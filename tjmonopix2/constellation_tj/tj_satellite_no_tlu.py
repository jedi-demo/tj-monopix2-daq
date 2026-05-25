from constellation.core.configuration import Configuration
from constellation.core.protocol.cscp1 import SatelliteState
from constellation.core.monitoring import schedule_metric
from constellation.core.transmitter_satellite import TransmitterSatellite
from constellation.core.message.cdtp2 import DataRecord
#from constellation.core.satellite import Satellite

import time
from tjmonopix2.scans.scan_source import SourceScan
import threading
import yaml
import os
from typing import Any


class TJMonopix2(TransmitterSatellite):
#class TJMonopix2(Satellite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_scan = None
        self.thread_scan = None

    def do_initializing(self, config: Configuration) -> str:
        try:
            self.source_scan.close()
        except AttributeError:
            pass
        self._load_config(config)
        return "initializing done"

    def do_launching(self) -> str:
        time.sleep(10)
        self.source_scan = SourceScan(scan_config=self.scan_configuration, bench_config=self.bench_conf)
        self.source_scan.init()
        self.source_scan._init_environment()
        self.source_scan._init_hardware(force=False)
        self.source_scan.initialized = True
        self.source_scan.configure()
        return "launching done"

    #def do_reconfigure(self, config: Configuration) -> str:
       # self.source_scan.close()
       # self._load_config(config)
       # self.source_scan = SourceScan(scan_config=self.scan_configuration, bench_config=self.bench_conf)
       # self.source_scan.init()
        #return "reconfiguring done"    

    def do_starting(self, run_identifier: str) -> str:
        self.log.info(f"do_starting: Starting {run_identifier}")
        self.source_scan._init_files()
        if hasattr(self.source_scan, "stop_scan"):
            self.source_scan.stop_scan.clear()
        self.thread_scan = threading.Thread(target=self.source_scan.scan)
        self.thread_scan.start()

        #time.sleep(60)
        # need to make sure scan is started before continuing
        # obviously sleep is not good enough
        return "starting done"

    def do_run(self) -> str:
        # HERE we need to send the data from TJmonopix to constellation
        # need to send data records via CDTP
        # we time out waiting for the BOR data record
        # only DATA messages need to be implemented, both BOR and EOR are handled automatically
         

        while not self._state_thread_evt.is_set():
        #while not self.stop_requested():
            time.sleep(1)
        return "datataking finished"
        
    def do_stopping(self) -> str:
        assert self.source_scan is not None
        assert self.thread_scan is not None
        self.source_scan.stop_scan.set()
        self.thread_scan.join()
        return "stopping done"

    def do_landing(self) -> str:
        assert self.source_scan is not None
        self.source_scan.analyze()
        return "landing done"

    def fail_gracefully(self) -> None:
        self.log.info("fail_gracefully: Failing gracefully")
        if self.source_scan is not None:
            self.source_scan.stop_scan.set()
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
            'start_column': config.get_int(key='start_column'),
            'stop_column': config.get_int(key='stop_column'),
            'start_row': config.get_int(key='start_row'),
            'stop_row': config.get_int(key='stop_row'),

            'scan_timeout': config.get_int(key='scan_timeout'),
            'max_triggers': config.get_int(key='max_triggers'),

            'tot_calib_file': config.get(key='tot_calib_file'),
            #'trigger_mode': config.get('trigger_mode'),
        }

        with open(config.get_path(key='testbench_path', check_exists=True), 'r') as f:
            self.bench_conf = yaml.full_load(f)
            self.bench_conf['general']['output_directory'] = config.get(key='output_directory')
            self.bench_conf['modules']['module_0']['chip_0']['chip_config_file'] = config.get('chip_config_file')
            self.bench_conf['modules']['module_0']['chip_0']['chip_sn'] = config.get('chip_sn')
            self.bench_conf['modules']['module_0']['chip_0']['send_data'] = config.get('send_data')
            self.bench_conf['analysis']['create_pdf'] = config.get('create_pdf')

    def receive_bor(self, sender: str, user_tags: dict[str, Any], configuration: dict[str, Any]) -> None:
        pass

    def receive_data(self, sender: str, data_record: DataRecord) -> None:
        pass

    def receive_eor(self, sender: str, user_tags: dict[str, Any], run_metadata: dict[str, Any]) -> None:
        pass
 

