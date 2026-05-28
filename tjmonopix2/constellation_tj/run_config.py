#!/usr/bin/env python3

import time

from constellation.core.controller import ScriptableController
from constellation.core.controller_configuration import load_config
from constellation.core.protocol.cscp1 import SatelliteState

# Settings
config_file_path = "/home/pixlab/constellation/configdgmrun.toml"
group_name = "edda"

# Create controller
ctrl = ScriptableController(group_name)

# Load configuration
cfg = load_config(config_file_path)
#print(cfg)
print("Configuration loaded")

# Wait until all satellites are connected
ctrl.await_satellites(["TTiQLSatellite.TTiQL", "TTiQLSatellite.TTiQL2", "Influx.DB", "TJMonopix2.chip0"])
#ctrl.await_satellites(["Influx.DB", "TJMonopix2.chip0"])
print("Satellites connected")
# Initialize and launch
ctrl.constellation.initialize(cfg)
print("Satellites initializing")
ctrl.await_state(SatelliteState.INIT)
print("Satellites initialized")
ctrl.constellation.launch()
print("Satellites launching")
ctrl.await_state(SatelliteState.ORBIT)
print("Satellites launched")

chip = ctrl.constellation.TJMonopix2.chip0
time.sleep(20)
# One scan per run: change scan_mode with reconfigure, then start with a run name
monopix_scans = ("analog", "analog", "tune_global", "tune_local", "threshold", "source")
for scan_mode in monopix_scans:
    chip.reconfigure({"scan_mode": scan_mode})
    print(f"Scan mode {scan_mode} configured")
    ctrl.await_state(SatelliteState.ORBIT)
    print("TJMP2 launched")
    #chip.start(f"calib_{scan_mode}")
    ctrl.constellation.start(f"calib_{scan_mode}")
    print("Run started")
    ctrl.await_state(SatelliteState.RUN)
    print("Running")

    while True:
        status = chip.get_status()
        if status.success and status.msg and "scan completed" in status.msg.lower():
            break
        time.sleep(1)

    ctrl.constellation.stop()
    print("Run finished")
    ctrl.await_state(SatelliteState.ORBIT)
    print("Satellites in orbit")

# Land and shutdown satellites
ctrl.constellation.land()
ctrl.await_state(SatelliteState.INIT)
ctrl.constellation.shutdown()
