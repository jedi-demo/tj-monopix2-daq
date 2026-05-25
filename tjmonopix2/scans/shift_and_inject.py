#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

'''
    This module takes care of the mask shifting and injection of the supported chips
    in order to keep actual scans cleaner.
'''
import time 

def shift_and_inject(chip, n_injections, pbar=None, scan=None, masks=['injection', 'enable'], pattern='default', cache=False, skip_empty=True, PulseStartCnfg=19, wait_cycles=1, latency=1400, scan_param=None, values=[]):
    ''' Regular mask shift and analog injection function.

    Parameters:
    ----------
        chip : chip object
            Chip object
        n_injections : int
            Number of injections per loop.
        pbar : tqdm progressbar
            Tqdm progressbar
        scan_param_id : int
            Scan parameter id of actual scan loop
        masks : list
            List of masks ('injection', 'enable', 'hitbus') which should be shifted during scan loop.
        pattern : string
            Injection pattern ('default', 'hitbus', ...)
        cache : boolean
            If True use mask caching for speedup. Default is False.
        skip_empty : boolean
            If True skip empty mask steps for speedup. Default is True.
    '''
    i = 0
    for fe, active_pixels in chip.masks.shift_threaded(masks=masks, pattern=pattern, skip_empty=skip_empty, prefetch=20):
        if not fe == 'skipped':
            if scan_param:
                for n,v in enumerate(values):
                    scan.scan_param_id = i
                    scan.store_scan_par_values(scan_param_id=i, vcal_high=40, vcal_low=v) # FIX ME HACK
                    chip.registers[scan_param].write(v)
                    chip.inject(PulseStartCnfg=PulseStartCnfg, PulseStopCnfg=PulseStartCnfg + 512, repetitions=n_injections, wait_cycles=wait_cycles, latency=latency)
                    time.sleep(0.01) 
                    scan.fifo_readout.drain_fifo() # empty the FIFO, invoking the handle_data callback which will stamp the data with the current scan_param_id
                    pbar.update(100)
                    i += 1
            else:
                chip.inject(PulseStartCnfg=PulseStartCnfg, PulseStopCnfg=PulseStartCnfg + 512, repetitions=n_injections, wait_cycles=wait_cycles, latency=latency)
    print(f"this many loops: {i}")
        

def get_scan_loop_mask_steps(chip, pattern='default'):
    ''' Returns total number of mask steps for specific pattern

    Parameters:
    ----------
        chip : chip object
            Chip object
        pattern : string
            Injection pattern ('default', 'hitbus', ...)
    '''

    return chip.masks.get_mask_steps(pattern=pattern)
