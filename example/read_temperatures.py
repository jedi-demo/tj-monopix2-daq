'''
    This minimal script shows how to read bdaq53 FPGA and chipboard NTC temperatures
    https://gitlab.cern.ch/silab/bdaq53/-/wikis/More/NTC-readout
'''

import os
import yaml
from tjmonopix2.system.bdaq53 import BDAQ53
from tjmonopix2.system.tjmonopix2 import TJMonoPix2

# Initialization
with open(os.path.join('..', 'tjmonopix2', 'system', 'bdaq53.yaml'), 'r') as f:
    cnfg = yaml.full_load(f)

daq = BDAQ53(cnfg)
daq.init()

# Read BDAQ FPGA temperature
print('BDAQ FPGA temperature = {0:1.2f}°C'.format(daq.get_temperature_FPGA()))
print()

if daq.enable_NTC:
    portnum = 7 # DP_ML 5 port (near mDP)
    print(f'Chipboard NTC temperature = {daq.get_temperature_NTC(portnum):.2f}°C')

# Closing
daq.close()
