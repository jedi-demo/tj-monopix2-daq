"""Threshold-distribution comparison
    python compare_threshold.py -d output_data/module_7/chip_0
    python compare_threshold.py scan_A_interpreted.h5 --ref 20260915_103000
    python compare_threshold.py scan_A_interpreted.h5 --ref /path/scan_B_interpreted.h5
"""

import argparse
import glob
import os
import re

import matplotlib
import matplotlib.colors
import matplotlib.ticker
import numpy as np
import tables as tb
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from scipy.optimize import curve_fit

from tjmonopix2.analysis import analysis_utils as au

SCURVE_CHI2_UPPER_LIMIT = 50
TITLE_COLOR = '#07529a'
OVERTEXT_COLOR = '#07529a'
REF_COLOR = 'tab:orange'      
CUR_FIT_COLOR = 'red'        
THRESHOLD_SCAN_RE = re.compile(r'^\d{8}_\d{6}_threshold_scan_interpreted\.h5$')


# ----------------------------------------------------------------- file handling
def to_interpreted(file_path):
    if file_path.endswith('_interpreted.h5'):
        return file_path
    return file_path.rsplit('.h5', 1)[0] + '_interpreted.h5'


def list_threshold_scans(directory):
    return sorted(os.path.join(directory, f) for f in os.listdir(directory) if THRESHOLD_SCAN_RE.match(f))


def resolve_reference(ref, current, directory):
    """'auto' -> previous threshold_scan; otherwise path, file name or timestamp token."""
    if ref == 'auto':
        earlier = [f for f in list_threshold_scans(directory) if os.path.basename(f) < os.path.basename(current)]
        return earlier[-1] if earlier else None
    if os.path.isfile(ref):
        return to_interpreted(ref)
    if os.path.isfile(os.path.join(directory, ref)):
        return to_interpreted(os.path.join(directory, ref))
    matches = sorted(glob.glob(os.path.join(directory, '*%s*_interpreted.h5' % ref)))
    return matches[-1] if matches else None


def load_scan(file_path):
    """Read what is needed from an interpreted threshold scan (same selection as Plotting)."""
    with tb.open_file(file_path, 'r') as f:
        root = f.root
        scan_config = au.ConfigDict(root.configuration_in.scan.scan_config[:])
        run_config = au.ConfigDict(root.configuration_in.scan.run_config[:])
        use_pixel = root.configuration_in.chip.use_pixel[:]
        try:
            scan_params = root.configuration_in.scan.scan_params[:]
        except tb.NoSuchNodeError:
            scan_params = None
        threshold = root.ThresholdMap[:, :]
        chi2 = root.Chi2Map[:, :]
        try:
            conv = au.ConfigDict(root.configuration_in.bench.electron_conversion[:])
        except tb.NoSuchNodeError:
            conv = None

    # Plotting._mask_disabled_pixels
    mask = np.invert(use_pixel)
    mask[:scan_config['start_column'], :] = True
    mask[scan_config['stop_column']:, :] = True
    mask[:, :scan_config['start_row']] = True
    mask[:, scan_config['stop_row']:] = True

    n_enabled = len(mask[~mask])
    sel = (chi2 > 0) & (chi2 < SCURVE_CHI2_UPPER_LIMIT) & (~mask)

    # Plotting.scan_parameter_range
    if scan_params is not None and 'VCAL_LOW' in scan_params.dtype.names:
        param_range = np.array(scan_params['VCAL_HIGH'] - scan_params['VCAL_LOW'], dtype=float)
    elif 'VCAL_LOW_start' in scan_config:
        param_range = [scan_config['VCAL_HIGH'] - v for v in
                       range(scan_config['VCAL_LOW_start'],
                             scan_config['VCAL_LOW_stop'] - 1,
                             scan_config['VCAL_LOW_step'])]
    else:
        param_range = None

    # Plotting electron conversion
    e_factor = None
    if conv is not None:
        c0, c1 = scan_config['start_column'], scan_config['stop_column']
        if c0 in range(448, 512) and c1 in range(448, 512):
            e_factor = conv['AC_coupled']
        else:
            e_factor = conv['DC_coupled']

    return {
        'file': file_path,
        'run_name': run_config['run_name'],
        'chip_sn': run_config['chip_sn'],
        'data': threshold[sel].T,
        'n_failed': n_enabled - len(chi2[sel]),
        'param_range': param_range,
        'e_factor': e_factor,
    }


# ----------------------------------------------------------------------- plotting
def convert_to_e(dac, factor):
    """Same as Plotting._convert_to_e (use_offset=False)."""
    return dac * factor, dac * factor * 0.15


def add_text(fig, chip_sn, level='preliminary'):
    """Same as Plotting._add_text."""
    fig.subplots_adjust(top=0.85)
    y_coord = 0.92
    fig.text(0.1, y_coord, '{0} {1}'.format('TJ-Monopix2', level), fontsize=12, color=OVERTEXT_COLOR, transform=fig.transFigure)
    fig.text(0.7, y_coord, 'Chip S/N: {0}'.format(chip_sn), fontsize=12, color=OVERTEXT_COLOR, transform=fig.transFigure)


def add_electron_axis(fig, ax, factor):
    """Same as Plotting._add_electron_axis."""
    fig.subplots_adjust(top=0.75)
    ax.title.set_position([.5, 1.15])

    fig.canvas.draw()
    ax2 = ax.twiny()

    xticks = []
    for t in ax.get_xticks(minor=False):
        xticks.append(int(convert_to_e(float(t), factor)[0]))

    ax2.set_xticklabels(xticks)

    l1 = ax.get_xlim()
    l2 = ax2.get_xlim()

    def f(x):
        return l2[0] + (x - l1[0]) / (l1[1] - l1[0]) * (l2[1] - l2[0])

    ticks = f(ax.get_xticks())
    ax2.xaxis.set_major_locator(matplotlib.ticker.FixedLocator(ticks))
    ax2.set_xlabel('Electrons', labelpad=7)
    return ax2


def fit_gauss(data, bins_in, do_fit=True):
    """Histogram data on bins_in and fit a gaussian.

    The initial guess comes from the data themselves (max, mean, std of the
    values) instead of the centre/width of the bin range, which makes the fit
    converge also when a scan is shifted or narrower than the plot range.
    """
    data = np.ravel(data)
    data = data[np.isfinite(data) & (data < 1e5)]
    hist, bins = np.histogram(data, bins=bins_in)
    bin_centres = (bins[:-1] + bins[1:]) / 2
    if not do_fit:
        return hist, bins, None
    p0 = (np.amax(hist), np.mean(data), max(np.std(data), 1e-3))
    try:
        coeff, _ = curve_fit(au.gauss, bin_centres, hist, p0=p0)
    except Exception:
        coeff = None
        print('Gauss fit failed!')
    return hist, bins, coeff


def fmt_e(dac, factor):
    e, de = convert_to_e(dac, factor)
    return '{0:1.0f} \\pm {1:1.0f}'.format(e, de)


def box_text(data, coeff, n_failed, factor, header, show_fit=True):
    """Compact text for one scan (same quantities as the original text box)."""
    d = data[np.isfinite(data) & (data < 1e5)]
    mean, rms = np.nanmean(d), np.nanstd(d)

    def line(sym, val):
        if factor:
            return '${0}={1:1.2f}\\;\\Delta$VCAL $=({2})\\;e^-$'.format(sym, val, fmt_e(val, factor))
        return '${0}={1:1.2f}\\;\\Delta$VCAL'.format(sym, val)

    lines = [header, line('\\mu', mean), line('\\sigma', rms)]
    if not show_fit:
        pass
    elif coeff is not None:
        lines += ['Fit:', line('\\mu', abs(coeff[1])), line('\\sigma', abs(coeff[2]))]
    else:
        lines += ['Fit: failed']
    lines += ['Failed fits: {0}'.format(n_failed), '# of pixels: {0}'.format(len(d))]
    return '\n'.join(lines)


def plot_comparison(cur, ref, draw_fit=True):
    plot_range = cur['param_range']
    if plot_range is None:
        raise SystemExit('Could not determine the scan parameter range of the current scan.')
    ref_range = ref['param_range'] if ref['param_range'] is not None and len(ref['param_range']) > 1 else plot_range
    factor = cur['e_factor']  # electron axis (like the original) uses the current scan's factor

    fig = Figure(figsize=(9.6, 4.8))  # wider than the default to make room for the legend on the right
    FigureCanvas(fig)
    ax = fig.add_subplot(111)
    add_text(fig, cur['chip_sn'])
    fig.subplots_adjust(right=0.6)  # free strip on the right, like the TDAC colorbar page

    # ---- current scan: same drawing as the original plot
    hist, bins, coeff = fit_gauss(cur['data'], plot_range, do_fit=draw_fit)
    ax.bar(bins[:-1], hist, width=np.diff(plot_range)[0], align='edge', color='tab:blue')

    # ---- reference scan: outline + dashed fit, on ITS OWN bins (so the fit is not truncated)
    ref_hist, ref_bins, ref_coeff = fit_gauss(ref['data'], ref_range, do_fit=draw_fit)
    ref_edges = np.append(ref_hist, ref_hist[-1])
    ax.fill_between(ref_bins, ref_edges, step='post', color=REF_COLOR, alpha=0.35, linewidth=0)
    ax.step(ref_bins, ref_edges, where='post', color=REF_COLOR, linewidth=1.5)

    x_min = min(np.min(plot_range), np.min(ref_range))
    x_max = max(np.max(plot_range), np.max(ref_range))
    points = np.linspace(x_min, x_max, 500)
    if coeff is not None:
        ax.plot(points, au.gauss(points, *coeff), '-', color=CUR_FIT_COLOR, linewidth=1.0, alpha=0.75)
    if ref_coeff is not None:
        ax.plot(points, au.gauss(points, *ref_coeff), '--', color=CUR_FIT_COLOR, linewidth=1.0, alpha=0.75)

    ax.set_xlim(x_min, x_max)
    ax.set_title('Threshold distribution for enabled pixels (comparison)', color=TITLE_COLOR)
    ax.set_xlabel('$\\Delta$ VCAL')
    ax.set_ylabel('# of pixels')
    ax.grid(True)

    # ---- legend to the right of the plot (outside the axes), both scans stacked
    cur_props = dict(boxstyle='round', facecolor='wheat', edgecolor='tab:blue', linewidth=1.2, alpha=0.6)
    ref_props = dict(boxstyle='round', facecolor='white', edgecolor=REF_COLOR, linewidth=1.2, alpha=0.8)
    ax.text(1.04, 1.0, box_text(cur['data'], coeff, cur['n_failed'], factor, 'Current:\n' + cur['run_name'], show_fit=draw_fit),
            transform=ax.transAxes, fontsize=7, verticalalignment='top', bbox=cur_props)
    ax.text(1.04, 0.5, box_text(ref['data'], ref_coeff, ref['n_failed'], ref['e_factor'], 'Reference:\n' + ref['run_name'], show_fit=draw_fit),
            transform=ax.transAxes, fontsize=7, verticalalignment='top', bbox=ref_props)

    if factor:
        add_electron_axis(fig, ax, factor)
    return fig


# --------------------------------------------------------------------------- main
def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('current', nargs='?', default=None,
                   help='current scan (raw or interpreted .h5). Default: latest threshold_scan in -d')
    p.add_argument('-d', default='./output_data/module_8/chip_0', help='directory with the scans')
    p.add_argument('--ref', default='auto',
                   help='reference scan: "auto" (previous threshold_scan), file path, file name or timestamp')
    p.add_argument('--out', default=None, help='output PDF (default: <current>_threshold_comparison.pdf)')
    p.add_argument('--no-fit', action='store_true', help='do not draw the gaussian fits (nor list fit results in the legend)')
    p.add_argument('--png', action='store_true', help='also save a PNG')
    return p.parse_args()


def main():
    args = parse_args()

    if args.current:
        current = to_interpreted(args.current)
    else:
        scans = list_threshold_scans(args.d)
        if not scans:
            raise SystemExit('No interpreted threshold_scan found in %s' % args.d)
        current = scans[-1]
    if not os.path.isfile(current):
        raise SystemExit('Current file not found: %s' % current)
    directory = os.path.dirname(os.path.abspath(current))

    ref = resolve_reference(args.ref, current, directory)
    if ref is None or not os.path.isfile(ref):
        raise SystemExit('No reference threshold_scan found (ref=%s)' % args.ref)
    if os.path.abspath(ref) == os.path.abspath(current):
        raise SystemExit('Reference and current scan are the same file.')

    print('Current  :', os.path.basename(current))
    print('Reference:', os.path.basename(ref))

    fig = plot_comparison(load_scan(current), load_scan(ref), draw_fit=not args.no_fit)

    out = args.out or current.rsplit('_interpreted.h5', 1)[0] + '_threshold_comparison.pdf'
    with PdfPages(out) as pdf:
        pdf.savefig(fig)
    if args.png:
        fig.savefig(out[:-4] + '.png')
    print('Saved:', out)


if __name__ == '__main__':
    main()
