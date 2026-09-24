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
import yaml, json, argparse

scan_configuration = {
    'start_column': 200,
    'stop_column': 202,
    'start_row': 0,
    'stop_row': 512,

    'n_injections': 100,
    'VCAL_HIGH': 140,
    'VCAL_LOW_start': 140,
    'VCAL_LOW_stop': 0,
    'VCAL_LOW_step': -1,
    'chip': {
        'registers': {
            'IBIAS': 250,
            'ITHR': 0
            }
    }
}

scan_configuration_per_chip = {
    'module_0': {
        'chip_0': {
            
            'chip': {
                'registers': {
                    'IBIAS': 104
                }
            }
        },
        'chip_1': {
            
            'chip': {
                'registers': {
                    'IBIAS': 104
                }
            }
        }
    }
}

class ThresholdScan(ScanBase):
    scan_id = 'threshold_scan'

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['injection'][start_column:stop_column, start_row:stop_row] = True

        # # Read masked pixels from masked_pixels.yaml
        with open("output_data/module_0/chip_0/masked_pixels.yaml") as f:
            masked_pixels = yaml.full_load(f)

        for i in range(0, len(masked_pixels['masked_pixels'])):
            row = masked_pixels['masked_pixels'][i]['row']
            col = masked_pixels['masked_pixels'][i]['col']
            self.chip.masks.disable_mask[col, row] = False
           # self.chip.masks['tdac'][col, row] = 0 # --> Max solution to disable the pixel BUT not store in use_pixel NOR in masks.enable


        col_bad = []
        # W8R6 bad columns (246 to 251 included: double-cols will be disabled)
        col_bad += [44]
        col_bad += [45]
        col_bad += [118]
        col_bad += [119]
        col_bad += [239]
        col_bad += [240]
        # # W8R13 pixels that fire even when disabled
        # col_bad += list(range(383,415)) # chip w8r13
        # col_bad += list(range(0,40)) # chip w8r13
        # col_bad += list(range(448,512)) # HV col disabled
        # Disable readout for double-columns of col_disabled and those outside start_column:stop_column
        col_disabled = col_bad
        col_disabled += list(range(0, start_column & 0xfffe))
        col_disabled += list(range((stop_column + 1) & 0xfffe, 512))
        reg_values = [0xffff] * 16
        for col in col_disabled:
            dcol = col // 2
            reg_values[dcol//16] &= ~(1 << (dcol % 16))
        # print(" ".join(f"{x:016b}" for x in reg_values))
        for i, v in enumerate(reg_values):
            #print(f"test i {enumerate(reg_values)}")
            # EN_RO_CONFsource /home/labb2/tj-monopix2-daq-development/venv/bin/activate
            self.chip._write_register(155+i, v)
            # EN_BCID_CONF (to disable BCID distribution on cols under test, use 0 instead of v, doing this the TOT is 0 since Le and trailing edge are not assigned BCID is missing)
            # To enable it all the matrix (higher I_LV and Temp), use  self.chip._write_register(171+i, 0xffff)
            # To enable only the used columns, use  self.chip._write_register(171+i, v)
            # To disable BCID distribution in all columns, use  self.chip._write_register(171+i, 0)
            self.chip._write_register(171+i, v)
            #self.chip._write_register(171+i, 0xffff)
            #self.chip._write_register(171+i, 0)
            # EN_RO_RST_CONF
            self.chip._write_register(187+i, v)
            # EN_FREEZE_CONF
            self.chip._write_register(203+i, v)
            # Read back
            # print(f"{i:3d} {v:016b} {self.chip._get_register_value(155+i):016b} {self.chip._get_register_value(171+i):016b} {self.chip._get_register_value(187+i):016b} {self.chip._get_register_value(203+i):016b}")



        self.chip.masks.apply_disable_mask()
        self.chip.masks.update(force=True)

        # # # # W8R06 irradiated HVC used TB2024 run 1566 TH=15.9 @30C and also W8R04
        # self.chip.registers["IBIAS"].write(100)
        #self.chip.registers["ITHR"].write(100) #def 30
        # self.chip.registers["ICASN"].write(30) #def 30
        # self.chip.registers["IDB"].write(100)
        # self.chip.registers["ITUNE"].write(250)
        # self.chip.registers["IDEL"].write(88)
        # self.chip.registers["IRAM"].write(50)
        # self.chip.registers["VRESET"].write(50)
        # self.chip.registers["VCASP"].write(40)
        # self.chip.registers["VCASC"].write(140)
        # self.chip.registers["VCLIP"].write(255)

        # # W8R06 irradiated DCC used TB2024 run 1484 THR=30.6 DAC  and also W8R04
        self.chip.registers["IBIAS"].write(250)
        self.chip.registers["ITHR"].write(0)  # TB ITHR=64
        self.chip.registers["ICASN"].write(60)  # TB ICASN=20
        # self.chip.registers["IDB"].write(100)  # TB IDB=100
        # self.chip.registers["ITUNE"].write(250)
        # self.chip.registers["IDEL"].write(88)  #prebvious lab test data with 88
        # self.chip.registers["IRAM"].write(50)
        # self.chip.registers["VRESET"].write(143) # TB 143
        # self.chip.registers["VCASP"].write(93)
        # self.chip.registers["VCASC"].write(205)
        # self.chip.registers["VCLIP"].write(255)

        # # # configuration to monitor ITUNE
        # self.chip.registers["MON_EN_ITUNE"].write(1)
        # self.chip.registers["OVR_EN_ITUNE"].write(0)

        # # configuration to overwrite ITUNE
        # self.chip.registers["MON_EN_ITUNE"].write(0)
        # self.chip.registers["OVR_EN_ITUNE"].write(1) # 1 se voglio abilitare OVRITUNE
        self.chip.registers["SEL_PULSE_EXT_CONF"].write(0)

    def _scan(self, n_injections=100, VCAL_HIGH=80, VCAL_LOW_start=80, VCAL_LOW_stop=40, VCAL_LOW_step=-1, **_):
        """
        Injects charges from VCAL_LOW_START to VCAL_LOW_STOP in steps of VCAL_LOW_STEP while keeping VCAL_HIGH constant.
        """

        self.chip.registers["VH"].write(VCAL_HIGH)
        vcal_low_range = range(VCAL_LOW_start, VCAL_LOW_stop, VCAL_LOW_step)

        pbar = tqdm(total=get_scan_loop_mask_steps(self.chip) * len(vcal_low_range), unit='Mask steps')
        for scan_param_id, vcal_low in enumerate(vcal_low_range):
            self.chip.registers["VL"].write(vcal_low)

            self.store_scan_par_values(scan_param_id=scan_param_id, vcal_high=VCAL_HIGH, vcal_low=vcal_low)
            with self.readout(scan_param_id=scan_param_id):
                shift_and_inject(chip=self.chip, n_injections=n_injections, pbar=pbar, scan_param_id=scan_param_id)
        pbar.close()
        self.log.success('Scan finished')

    def _analyze(self):
        with analysis.Analysis(raw_data_file=self.output_filename + '.h5', **self.configuration['bench']['analysis']) as a:
            a.analyze_data()

        if self.configuration['bench']['analysis']['create_pdf']:
            with plotting.Plotting(analyzed_data_file=a.analyzed_data_file) as p:
                p.create_standard_plots()


if __name__ == "__main__":
    #with ThresholdScan(scan_config=scan_configuration,scan_config_per_chip=scan_configuration_per_chip) as scan:
    with ThresholdScan(scan_config=scan_configuration) as scan:
        scan.start()
