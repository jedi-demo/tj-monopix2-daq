#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#
import threading
from tjmonopix2.analysis import analysis, plotting
from tjmonopix2.scans.shift_and_inject import (get_scan_loop_mask_steps,
                                               shift_and_inject)
from tjmonopix2.system.scan_base import ScanBase
from tjmonopix2.scans.scan_threshold import ThresholdScan
from tjmonopix2.scans.scan_analog import AnalogScan
from tjmonopix2.scans.tune_global_threshold import GDACTuning
from tjmonopix2.scans.tune_local_threshold import TDACTuning
from tqdm import tqdm

scan_configuration = {
    #'chip_sn': "chipSN",
    'start_column': 300,
    'stop_column': 301,
    'start_row': 0,
    'stop_row': 512,

    'n_injections': 100,

    # Target threshold
    # injected charge is proportional to VCAL_HIGH - VCAL_LOW
    # for normal cascode, 9 electrons per DAC unit
    # 35 - 24 = 11 -> 11 * 9 = 99 electrons
    'VCAL_LOW': 24,
    'VCAL_HIGH': 35,

    # This setting does not have to be changed, it only allows (slightly) faster retuning
    # E.g.: gdac_value_bits = [3, 2, 1, 0] uses the 4th, 3rd, 2nd, and 1st GDAC value bit.
    # GDAC is not an existing DAC, its value is mapped to ITHR currently
    'gdac_value_bits': range(6, -1, -1),

    # range in VCAL to scan during threshold scan:
    # delta VCAL: (VCAL_HIGH - VCAL_LOW_start) - (VCAL_HIGH - VCAL_LOW_stop)
    'VCAL_LOW_start': 1,
    'VCAL_LOW_stop': 34,
    'VCAL_LOW_step': -1
}


class CalibrationScan():
    scan_id = 'calibration_scan'
    stop_scan = threading.Event()

    def __init__(self, scan_config, bench_config=None):
        self.scan_config = scan_config
        self.bench_config = bench_config

    def run_calibrations(self):
        try:
            with AnalogScan(scan_config=self.scan_config) as scan:
                scan.start()
        except:
            pass
        with GDACTuning(scan_config=self.scan_config) as scan:
            scan.start()
        with TDACTuning(scan_config=self.scan_config) as scan:
            scan.start()
        with ThresholdScan(scan_config=self.scan_config) as scan:
            scan.start()


if __name__ == "__main__":
    scan = CalibrationScan(scan_config=scan_configuration)
    scan.run_calibrations()
