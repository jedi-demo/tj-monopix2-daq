#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

from tjmonopix2.analysis import analysis, plotting
from tjmonopix2.scans.shift_and_inject import (get_scan_loop_mask_steps,
                                               shift_and_inject)
from tjmonopix2.system.scan_base import ScanBase
from tqdm import tqdm
from time import perf_counter
from contextlib import contextmanager
from collections import defaultdict

@contextmanager
def timed(label, acc):
    t0 = perf_counter()
    try:
        yield
    finally:
        acc[label] += perf_counter() - t0
scan_configuration = {
    'start_column': 300,
    'stop_column': 301,
    'start_row': 0,
    'stop_row': 512,

    'n_injections': 100,
    'VCAL_HIGH': 130,
    'VCAL_LOW_start': 110,
    'VCAL_LOW_stop': 40,
    'VCAL_LOW_step': -1
    # delta VCAL: (VCAL_HIGH - VCAL_LOW_start) - (VCAL_HIGH - VCAL_LOW_stop)
}


class ThresholdScan(ScanBase):
    scan_id = 'threshold_scan'

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['injection'][start_column:stop_column, start_row:stop_row] = True

        self.chip.masks.apply_disable_mask()
        self.chip.masks.update(force=True)

        self.chip.registers["SEL_PULSE_EXT_CONF"].write(0)
        self.chip.registers["VCLIP"].write(60) # corresponds to max tot of 32


    def _scan(self, n_injections=100, VCAL_HIGH=80, VCAL_LOW_start=80, VCAL_LOW_stop=40, VCAL_LOW_step=-1, **_):
        self.timing = defaultdict(float)
        self.sandtiming = defaultdict(float)

        with timed("write_VH", self.timing):
            self.chip.registers["VH"].write(VCAL_HIGH)

        vcal_low_range = range(VCAL_LOW_start, VCAL_LOW_stop, VCAL_LOW_step)
        pbar = tqdm(total=get_scan_loop_mask_steps(self.chip) * len(vcal_low_range), unit="Mask steps")

        for scan_param_id, vcal_low in enumerate(vcal_low_range):
            with timed("write_VL", self.timing):
                self.chip.registers["VL"].write(vcal_low)

            with timed("store_scan_par_values", self.timing):
                self.store_scan_par_values(scan_param_id=scan_param_id, vcal_high=VCAL_HIGH, vcal_low=vcal_low)

            with timed("readout_block", self.timing):
                with self.readout(scan_param_id=scan_param_id):
                    with timed("shift_and_inject", self.timing):
                        sandtiming = shift_and_inject(
                            chip=self.chip,
                            n_injections=n_injections,
                            pbar=pbar,
                            scan_param_id=scan_param_id,
                            timing=self.timing
                        )
        pbar.close()
        self.log.success("Scan finished")

        print(dict(self.timing))
        for k, v in sorted(scan.timing.items(), key=lambda kv: kv[1], reverse=True):
            print(f"{k:35s} {v:12.6f}")
        return dict(self.timing)
    def _analyze(self):
        return
        with analysis.Analysis(raw_data_file=self.output_filename + '.h5', **self.configuration['bench']['analysis']) as a:
            a.analyze_data()

        if self.configuration['bench']['analysis']['create_pdf']:
            with plotting.Plotting(analyzed_data_file=a.analyzed_data_file) as p:
                p.create_standard_plots()


if __name__ == "__main__":
    with ThresholdScan(scan_config=scan_configuration) as scan:
        scan.start()
