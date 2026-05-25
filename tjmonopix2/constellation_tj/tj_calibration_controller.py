# This is example code, adapting...
# we want to implement:
#   - establish basic comms: register r/w
#   - analog test
#   - tune global
#   - tune local
#   - calibrate tot
#   - threshold scan
#   - noise masking

import time

from constellation.core.controller import ScriptableController
from constellation.core.controller_configuration import load_config
from constellation.core.listener import MonitoringListener
from constellation.core.protocol.cscp1 import SatelliteState

from tjmonopix2.scans.scan_ext_trigger import ExtTriggerScan

# Custom controller which listens to metrics
class TJCalibController(ScriptableController, MonitoringListener):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Subscribe to POST_VETO metric
        self.set_topics(["STAT/POST_VETO"])
        self.post_veto_triggers = 0

    def receive_metric(self, sender, metric, timestamp, value):
        if metric.name == "POST_VETO" and sender == "AidaTLU.2020":
            self.post_veto_triggers = value


# Settings
config_file_path = "/path/to/config.toml"
group_name = "edda"

# Create controller
ctrl = TJCalibController(group_name)

# Load configuration
cfg = load_config(config_file_path)

# Wait until all satellites are connected
ctrl.await_satellites(["TJMonoPix2"]) # and all the power supplies etc

# Initialize and launch
ctrl.constellation.initialize(cfg)
ctrl.await_state(SatelliteState.INIT)
ctrl.constellation.launch()
ctrl.await_state(SatelliteState.ORBIT)

# Scan over bias voltages
voltages = [-1.2, -2.4, -3.6, -4.8]
for voltage in voltages:
    # Reconfigure Keithley with new voltage
    recfg = {"voltage": voltage}

    # Store last state change for Keithley to ensure it reached reconfiguring
    last_state_change = ctrl.get_last_state_change(["Keithley.Bias"])

    # Send reconfigure command
    ctrl.constellation.Keithley.Bias.reconfigure(recfg)

    # Wait until all states are back in the ORBIT state while ensuring Keithley.Bias changed state
    ctrl.await_state_change(SatelliteState.ORBIT, last_state_change)

    # Start the run
    ctrl.constellation.start(f"voltage{str(voltage).replace('.', '_')}")
    ctrl.await_state(SatelliteState.RUN)

    # Wait until 1M triggers are collected
    while ctrl.post_veto_triggers < 1000000:
        time.sleep(1)

    # Stop the run and await ORBIT state of all satellites
    ctrl.constellation.stop()
    ctrl.await_state(SatelliteState.ORBIT)

# Land and shutdown satellites
ctrl.constellation.land()
ctrl.constellation.shutdown()


