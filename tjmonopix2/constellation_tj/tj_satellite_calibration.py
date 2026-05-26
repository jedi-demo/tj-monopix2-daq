from constellation.core.configuration import Configuration
from constellation.core.protocol.cscp1 import SatelliteState
from constellation.core.monitoring import schedule_metric
from constellation.core.transmitter_satellite import TransmitterSatellite
from constellation.core.message.cdtp2 import DataRecord

import time
from tjmonopix2.scans.scans_calibration import CalibrationScan
import threading
import yaml
import os
from typing import Any

"""
This is a calbiration satellite
"""

class TJMonopix2(TransmitterSatellite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calibration_scan = None
        self.thread_scan = None

    def do_initializing(self, config: Configuration) -> str:
        try:
            self.calibration_scan.close()
        except AttributeError:
            pass
        self._load_config(config)
        return "initializing done"


    def do_starting(self, run_identifier: str) -> str:
        self.log.info(f"do_starting: Starting {run_identifier}")
        self.calibration_scan = CalibrationScan(scan_config=self.scan_configuration, bench_config=self.bench_conf)
        if hasattr(self.calibration_scan, "stop_scan"):
            self.calibration_scan.stop_scan.clear()
        self.thread_scan = threading.Thread(target=self.calibration_scan.run_calibrations)
        self.thread_scan.start()

        self.bor["run_identifier"] = run_identifier
        return "starting done"

    def do_run(self) -> str:
        while not self._state_thread_evt.is_set():
            time.sleep(1)
        return "datataking finished"
        
    def do_stopping(self) -> str:
        assert self.calibration_scan is not None
        assert self.thread_scan is not None
        if hasattr(self.calibration_scan, "stop_scan"):
            self.calibration_scan.stop_scan.set()
        self.thread_scan.join()
        return "stopping done"

    def do_landing(self) -> str:
        assert self.calibration_scan is not None
        return "landing done"

    def fail_gracefully(self) -> None:
        self.log.info("fail_gracefully: Failing gracefully")
        if self.calibration_scan is not None:
            self.calibration_scan.stop_scan.set()
            self.log.info("fail_gracefully: stop_scan set")
        if self.thread_scan is not None:
            self.thread_scan.join()
            self.log.info("fail_gracefully: Scan thread stopped")
        self.log.info("fail_gracefully: Failed gracefully.")

    def _load_config(self, config: Configuration) -> None:
        config.set_default(key='tot_calib_file', value=None)
        config.set_default(key='output_directory', value=None)
        config.set_default(key='chip_config_file', value=None)
        config.set_default(key='testbench_path', value=os.path.join(os.path.join(os.path.dirname(__file__), '..'), 'testbench.yaml'))
        config.set_default(key='scan_timeout', value=False)

        config.set_default(key='send_data', value="tcp://127.0.0.1:5500")
        #config.set_default(key='trigger_mode', value="eudet") # !!!!
        config.set_default(key='create_pdf', value=True)

        self.scan_configuration = {
            'start_column': 300,
            'stop_column': 302,
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
            'VCAL_LOW_stop': 35,
            'VCAL_LOW_step': -1
        } 

        with open(config.get_path(key='testbench_path', check_exists=True), 'r') as f:
            self.bench_conf = yaml.full_load(f)
            self.bench_conf['general']['output_directory'] = config.get(key='output_directory')
            self.bench_conf['modules']['module_0']['chip_0']['chip_config_file'] = config.get('chip_config_file')
            self.bench_conf['modules']['module_0']['chip_0']['chip_sn'] = config.get('chip_sn')
            self.bench_conf['modules']['module_0']['chip_0']['send_data'] = config.get('send_data')
            self.bench_conf['analysis']['create_pdf'] = config.get('create_pdf')
