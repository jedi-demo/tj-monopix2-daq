from constellation.core.configuration import Configuration
from constellation.core.protocol.cscp1 import SatelliteState
from constellation.core.monitoring import schedule_metric
from constellation.core.transmitter_satellite import TransmitterSatellite
from constellation.core.message.cdtp2 import DataRecord

import time
import threading
import yaml
import os
from typing import Any, Type

from tjmonopix2.scans.scans_calibration import CalibrationScan
from tjmonopix2.scans.scan_analog import AnalogScan
from tjmonopix2.scans.scan_threshold import ThresholdScan
from tjmonopix2.scans.tune_global_threshold import GDACTuning
from tjmonopix2.scans.tune_local_threshold import TDACTuning
from tjmonopix2.system.scan_base import ScanBase
from tjmonopix2.scans.scan_source import SourceScan
from tjmonopix2.scans.scan_ext_trigger import ExtTriggerScan
from tjmonopix2.scans.scan_noise_occupancy import NoiseOccScan
from tjmonopix2.system.bdaq53 import BDAQ53
from tjmonopix2.system.tjmonopix2 import TJMonoPix2

SCAN_TYPES: dict[str, Type[ScanBase]] = {
    'all': CalibrationScan,
    'analog': AnalogScan,
    'tune_global': GDACTuning,
    'tune_local': TDACTuning,
    'threshold': ThresholdScan,
    'source': SourceScan,
    'ext_trigger': ExtTriggerScan,
    'noise_occ': NoiseOccScan,
}


class TJMonopix2(TransmitterSatellite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calibration_scan = None
        self.scan_mode = 'all'
        self.thread_scan = None
        self._scan_error: BaseException | None = None

    def do_initializing(self, config: Configuration) -> str:
        try:
            self.calibration_scan.close()
        except AttributeError:
            pass
        self._load_config(config)
        return 'initializing done'

    def do_reconfigure(self, partial_config: Configuration) -> str:
        if 'scan_mode' in partial_config:
            self.scan_mode = partial_config['scan_mode']
        
        if 'start_column' in partial_config:
            self.scan_configuration['start_column'] = int(partial_config['start_column'])
        if 'stop_column' in partial_config:
            self.scan_configuration['stop_column'] = int(partial_config['stop_column'])
        if 'start_row' in partial_config:
            self.scan_configuration['start_row'] = int(partial_config['start_row'])
        if 'stop_row' in partial_config:
            self.scan_configuration['stop_row'] = int(partial_config['stop_row'])
        if 'max_triggers' in partial_config:
            self.scan_configuration['max_triggers'] = int(partial_config['max_triggers']) 
        if 'scan_timeout' in partial_config:
            self.scan_configuration['scan_timeout'] = int(partial_config['scan_timeout'])
        
        return 'reconfiguring done'

    def do_starting(self, run_identifier: str) -> str:
        self.log.info(
            f'do_starting: run "{run_identifier}", scan_mode={self.scan_mode}'
        )
        self._scan_error = None

        self.calibration_scan = SCAN_TYPES[self.scan_mode](scan_config=self.scan_configuration, bench_config=self.bench_conf)

        if hasattr(self.calibration_scan, 'stop_scan'):
            self.calibration_scan.stop_scan.clear()

        self.thread_scan = threading.Thread(target=self._run_scan_work)
        self.thread_scan.start()

        self.bor['run_identifier'] = run_identifier
        self.bor['scan_mode'] = self.scan_mode
        return 'starting done'

    def do_run(self) -> str:
        assert self.thread_scan is not None
        while self.thread_scan.is_alive() and not self._state_thread_evt.is_set():
            self.thread_scan.join(timeout=0.5)

        if self.thread_scan.is_alive():
            return 'datataking interrupted'

        if self._scan_error is not None:
            raise self._scan_error

        self.fsm.status = 'Scan completed, awaiting stop'
        while not self._state_thread_evt.is_set():
            time.sleep(1)
        return 'datataking finished'

    def do_stopping(self) -> str:
        assert self.calibration_scan is not None
        assert self.thread_scan is not None
        if hasattr(self.calibration_scan, 'stop_scan'):
            self.calibration_scan.stop_scan.set()
        self.thread_scan.join()
        self.calibration_scan = None
        self.thread_scan = None
        return 'stopping done'

    def do_landing(self) -> str:
        return 'landing done'

    def fail_gracefully(self) -> None:
        self.log.info('fail_gracefully: Failing gracefully')
        if self.calibration_scan is not None and hasattr(self.calibration_scan, 'stop_scan'):
            self.calibration_scan.stop_scan.set()
            self.log.info('fail_gracefully: stop_scan set')
        if self.thread_scan is not None:
            self.thread_scan.join()
            self.log.info('fail_gracefully: Scan thread stopped')
        self.calibration_scan = None
        self.thread_scan = None
        self.log.info('fail_gracefully: Failed gracefully.')

    def _run_scan_work(self) -> None:
        try:
            assert self.calibration_scan is not None
            if self.scan_mode == 'all':
                self.calibration_scan.run_calibrations()
            else:
                with self.calibration_scan:
                    self.calibration_scan.start()
        except Exception as exc:
            self._scan_error = exc
            self.log.exception('Scan failed: %s', exc)


    def _load_config(self, config: Configuration) -> None:
        config.set_default(key='tot_calib_file', value=None)
        config.set_default(key='output_directory', value=None)
        config.set_default(key='chip_config_file', value=None)
        config.set_default(key='testbench_path', value=os.path.join(os.path.join(os.path.dirname(__file__), '..'), 'testbench.yaml'))
        config.set_default(key='scan_timeout', value=100)
        config.set_default(key='scan_mode', value='all')

        config.set_default(key='send_data', value='tcp://127.0.0.1:5500')
        #config.set_default(key='trigger_mode', value="eudet") # !!!!
        config.set_default(key='create_pdf', value=True)

        self.scan_mode = config.get('scan_mode')
        
        
        self.scan_configuration = {
            'start_column': config.get_int(key='start_column'),
            'stop_column': config.get_int(key='stop_column'),
            'start_row': config.get_int(key='start_row'),
            'stop_row': config.get_int(key='stop_row'),
            'max_triggers': config.get_int(key='max_triggers'),
            
            'scan_timeout': config.get_int(key='scan_timeout'),
            
            'min_occupancy': 1,
            
            'n_injections': 100,

            # This setting does not have to be changed, it only allows (slightly) faster retuning
            # E.g.: gdac_value_bits = [3, 2, 1, 0] uses the 4th, 3rd, 2nd, and 1st GDAC value bit.
            # GDAC is not an existing DAC, its value is mapped to ITHR currently
            'gdac_value_bits': range(6, -1, -1),

            # range in VCAL to scan during threshold scan:
            # delta VCAL: (VCAL_HIGH - VCAL_LOW_start) - (VCAL_HIGH - VCAL_LOW_stop)
            'VCAL_LOW': 24,
            'VCAL_HIGH': 130,
            'VCAL_LOW_start': 110,
            'VCAL_LOW_stop': 40,
            'VCAL_LOW_step': -1,
            
            #'tot_calib_file' : config.get_int(key='tot_calib_file'),
            #'output_directory' : config.get_int(key='output_directory'),
            #'chip_config_file' : config.get_int(key='chip_config_file'),
            #'testbench_path' : config.get_int(key='testbench_path'),
            #'send_data' : config.get_int(key='send_data'),
            #'trigger_mode' : config.get_int(key='trigger_mode'),
            #'create_pdf' : config.get_int(key='create_pdf'),
            #'tot_calib_file' : config.get_int(key='tot_calib_file'),

        }

        with open(config.get_path(key='testbench_path', check_exists=True), 'r') as f:
            self.bench_conf = yaml.full_load(f)
            self.bench_conf['general']['output_directory'] = config.get(key='output_directory')
            self.bench_conf['modules']['module_0']['chip_0']['chip_config_file'] = config.get('chip_config_file')
            self.bench_conf['modules']['module_0']['chip_0']['chip_sn'] = config.get('chip_sn')
            self.bench_conf['modules']['module_0']['chip_0']['send_data'] = config.get('send_data')
            self.bench_conf['analysis']['create_pdf'] = config.get('create_pdf')

    @schedule_metric("temperature_fpga", 1)
    def temperature_fpga(self) -> Any:
        if self.fsm.current_state_value != SatelliteState.RUN:
            return None
            
        if not self.calibration_scan or not getattr(self.calibration_scan, 'initialized', False):
            return None
            
        daq = getattr(self.calibration_scan, 'daq', None)
        if not daq:
            return None

        try:
            temp = float(daq.get_temperature_FPGA())
            limit_fpga = 60
            if temp >= limit_fpga:
                self.log.critical(f"FPGA at {temp}°C (Limit: {limit_fpga}°C)")
                self._scan_error = RuntimeError(f"FPGA overheating: {temp}°C")
                self.calibration_scan.stop_scan.set()
            return temp
        except Exception:
            return None

    @schedule_metric("temperature_ntc", 1)
    def temperature_ntc(self) -> Any:
        if self.fsm.current_state_value != SatelliteState.RUN:
            return None
            
        if not self.calibration_scan or not getattr(self.calibration_scan, 'initialized', False):
            return None
            
        daq = getattr(self.calibration_scan, 'daq', None)
        if not daq or not getattr(daq, 'enable_NTC', False):
            return None

        port = 7 
        limit_ntc = 45
        try:
            temp = float(daq.get_temperature_NTC(port))
            if temp >= limit_ntc:
                self.log.critical(f"NTC at {temp}°C (Limit: {limit_ntc}°C)")
                self._scan_error = RuntimeError(f"NTC overheating: {temp}°C")
                self.calibration_scan.stop_scan.set()
            return temp
            
        except Exception:
            return None
            
    @schedule_metric("ScanType", 1)
    def scantypemetric(self):
        if self.fsm.current_state_value == SatelliteState.ORBIT: 
            return "Orbiting"
        if self.fsm.current_state_value == SatelliteState.INIT: 
            return "Initialized"
        if not self.calibration_scan or not getattr(self.calibration_scan, 'initialized', False):
            return 
        if self.fsm.current_state_value == SatelliteState.RUN and self.calibration_scan: 
            return str(self.scan_mode)
        return
