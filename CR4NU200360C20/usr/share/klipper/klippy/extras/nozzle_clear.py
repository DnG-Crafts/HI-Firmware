# prtouch support
#
# Copyright (C) 2018-9999  Creality <wangyulong878@sina.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import sys
sys.path.append('../') 
import logging, statistics, time, socket, math, random, threading, datetime
from . import probe, bed_mesh, bus, homing, heaters
from mcu import *
from gcode import *
from toolhead import *
from stepper import *
from configfile import *


class NozzleClear:
    def __init__(self, config):
        self.config             = config
        self.printer            = config.get_printer()
        self.gcode              = self.printer.lookup_object('gcode')
        self.probe              = self.printer.lookup_object('probe')
        self.probe_pos_diff     = config.getintlist('probe_pos_diff', default=(-20, 6))
        self.clear_start        = config.getintlist('clear_start', default=(130, 264))
        self.clear_lenght       = config.getintlist('clear_lenght', default=(29, 2))
        self.clear_temp         = config.getint('clear_temp', default=140)
        self.clear_speed        = config.getfloat('clear_speed', default=6000)
        self.clear_cnt          = config.getint('clear_cnt', default=5)
        self.show_msg           = config.getboolean('show_msg', default=False)
        self.upraise            = config.getfloat('upraise', default=1)
        self.start_pos          = config.getintlist('start_pos', default=(110,260))
        self.start_clear_temp   = config.getint('start_clear_temp', default=175)
        self.touch_speed        = config.getint('touch_speed', default=15)
        self.touch_cnt          = config.getint('touch_cnt', default=4)
        self.pumpback_mm        = config.getint('pumpback_mm', default=3)
        self.retract_dist       = config.getint('retract_dist', default=2)
        self.enable_clear       = config.getboolean('enable_clear', default=False)
        self.zmax               = config.getsection('stepper_z').getfloat('position_max')
        self.extrude_length     = config.getint('extrude_length', default=50)
        self.extr_enable        = config.getboolean('extr_enable', default=False)
        self.touch_gain         = config.getfloat('touch_gain', default=1, minval=1.0, maxval=5.0)         # 热床上进行喷头擦拭时，两个定位点的触发压力要大些，此处是阈值比例
        self.closure_temp       = config.getfloat('closure_temp', default=120)
        self.inside_nozzle_clear= False
        if self.config.has_section("box"):
            self.extrude_pos_x      = config.getsection('box').getfloat('extrude_pos_x')
        self.gcode.register_command('NOZ_CLEAR', self.cmd_NOZZLE_CLEAR, desc=self.cmd_F018_NOZZLE_CLEAR_help)
        self.gcode.register_command('FORECEZ', self.cmd_FORECEZ, desc=self.cmd_F018_FORECEZ_help)
        pass
    
    cmd_F018_FORECEZ_help = "Before print ZDOWN and FORECEZ "  #文件打印前zdown和强制位移z
    def cmd_FORECEZ(self, gcmd):
        self.gcode.run_script_from_command('ZDOWN')
        for cnt_1 in range(10):
            for cnt_2 in range(10):
                self.gcode.run_script_from_command('FORCE_MOVE STEPPER=stepper_z DISTANCE=-0.1 VELOCITY=10')
                self.gcode.run_script_from_command('FORCE_MOVE STEPPER=stepper_z1 DISTANCE=-0.1 VELOCITY=10')
                pass 
        pass 
    
    def pnt_msg(self, msg):
        if self.show_msg:
            self.gcode.respond_info(msg)
        pass

    cmd_F018_NOZZLE_CLEAR_help = "Clear the nozzle on bed."
    def cmd_NOZZLE_CLEAR(self, gcmd):
        self.inside_nozzle_clear= True
        try:
            diff_pos_x = random.uniform(0, 3)
            diff_pos_y = random.uniform(0, 3)
            self.gcode.run_script_from_command('M204 S10000')
            # self.gcode.run_script_from_command('M104 S%d' %(self.start_clear_temp))
            #增大插嘴时的触发力度，增加抗干扰性
            prtouch_v3 = self.printer.lookup_object('prtouch_v3')
            old_hold = [v for v in prtouch_v3.pres.tri_hold] # 为防止喷头残留耗材带来的干扰，这里把触发阈值给大点，防止点到耗材就触发的情况
            prtouch_v3.pres.tri_hold = [int(v * self.touch_gain) for v in prtouch_v3.pres.tri_hold]
            self.gcode.respond_info(">>>new tri_hold = %s" % prtouch_v3.pres.tri_hold)

            self.gcode.run_script_from_command('M104 S0')
            toolhead = self.printer.lookup_object('toolhead')
            curtime = self.printer.get_reactor().monotonic()
            if 'xy' not in toolhead.get_status(curtime)['homed_axes']:
                self.gcode.run_script_from_command('G28 X Y')
            self.gcode.run_script_from_command('SET_KINEMATIC_POSITION Z=%d' %(self.zmax))
            self.gcode.run_script_from_command('G0 X%dY%d F12000' %(self.start_pos[0]-diff_pos_y, self.start_pos[1]+diff_pos_x))
            self.gcode.run_script_from_command('G0 Z%d F600' %(self.zmax - 0.01)) #解决Z轴不同步问题
            self.gcode.run_script_from_command('G4 P500')
            self.gcode.run_script_from_command('M400')
            # self.gcode.run_script_from_command('PROBE')
            self.gcode.run_script_from_command('ZHOME')   #ZHOME允许轴任意位置回零，相较于PROBE，在下探过程中会探测两次，两次误差太大会继续下探，防止误触发
            self.gcode.run_script_from_command('SET_KINEMATIC_POSITION Z=0')
            self.gcode.run_script_from_command('G0 Z10 F3000')

            #精擦
            if self.config.has_section("box") and self.extr_enable:
                self.gcode.run_script_from_command('G0 X%f F18000' %(self.extrude_pos_x))
                self.gcode.run_script_from_command('M109 S%d' %(self.start_clear_temp))
                self.gcode.run_script_from_command('G91')
                self.gcode.run_script_from_command('G0 E%d F400' %(self.extrude_length))
                self.gcode.run_script_from_command('G0 E-1') #回抽
                self.gcode.run_script_from_command('G90')
                self.gcode.run_script_from_command('M400')
                self.gcode.run_script_from_command('SET_PIN PIN=fan0 VALUE=127.0')
                self.gcode.run_script_from_command('G4 P1000')
                self.gcode.run_script_from_command('M400')
                self.gcode.run_script_from_command('G0 X10 F18000')
                self.gcode.run_script_from_command('G0 X%f' %(self.extrude_pos_x))
                self.gcode.run_script_from_command('G0 X10')
                pass
            self.gcode.run_script_from_command('G0 X%dY%d F18000' %(self.start_pos[0]-diff_pos_y, self.start_pos[1]+diff_pos_x))
            self.gcode.run_script_from_command('M109 S%d' %(self.start_clear_temp))
            self.gcode.run_script_from_command('G91')
            self.gcode.run_script_from_command('G0 E-%f' %(self.pumpback_mm)) #回抽
            self.gcode.run_script_from_command('G0 X2 F6000')
            for cnt in range(self.touch_cnt):
                for cnt2 in range(3):
                    self.gcode.run_script_from_command('G90 \nPROBE PROBE_SPEED=%d SAMPLE_RETRACT_DIST=%d'%(self.touch_speed,self.retract_dist))
                    if cnt2 == 2:
                        self.gcode.run_script_from_command('G91 \nG0 X2 F6000')
                    self.gcode.run_script_from_command('G91 \nG0 Z3X2 F3000')
                self.gcode.run_script_from_command('G91 \nG0 X3 F6000')
            self.gcode.run_script_from_command('G90 \nPROBE PROBE_SPEED=%d SAMPLE_RETRACT_DIST=%d'%(self.touch_speed,self.retract_dist))

            #粗擦
            self.gcode.run_script_from_command('G90')
            self.gcode.run_script_from_command('SET_PIN PIN=fan0 VALUE=127.0')
            self.gcode.run_script_from_command('M109 S%d'%(self.clear_temp))
            self.gcode.run_script_from_command('M104 S0')
            self.gcode.run_script_from_command('SET_PIN PIN=fan0 VALUE=0.0')
            self.gcode.run_script_from_command('G0 Z3 F300')
            check_pos = [self.clear_start[0] - 20, self.clear_start[1]]
            self.gcode.run_script_from_command('G0 X%fY%fF%d'%(check_pos[0], check_pos[1], self.clear_speed))
            self.gcode.run_script_from_command('PROBE')
            self.gcode.run_script_from_command('SET_KINEMATIC_POSITION Z=0')
            if self.enable_clear == True:
                check_pos = [self.clear_start[0], self.clear_start[1]]
                self.gcode.run_script_from_command('G0 X%fY%fF%d'%(check_pos[0], check_pos[1],self.clear_speed))
                self.gcode.run_script_from_command('G91')
                self.gcode.run_script_from_command('G0 X%fY%f F%f' %(self.probe_pos_diff[0], self.probe_pos_diff[1], self.clear_speed))
                self.gcode.run_script_from_command('G0 Z%f F300' %(self.upraise))
                self.gcode.run_script_from_command('G90')
                self.gcode.run_script_from_command('G0 F%f'%(self.clear_speed))
                self.gcode.run_script_from_command('G91')
                for i in range(self.clear_cnt):
                    self.gcode.run_script_from_command('G0 X%f'%(self.clear_lenght[0]))
                    self.gcode.run_script_from_command('G0 Y%f'%(self.clear_lenght[1]))
                    self.gcode.run_script_from_command('G0 X%f'%(-self.clear_lenght[0]))
                    self.gcode.run_script_from_command('G0 Y%f'%(-self.clear_lenght[1]))
                    pass
            self.gcode.run_script_from_command('G0 Z5 F300')  #擦完抬高回光平台封嘴
            check_pos = [self.clear_start[0] - 20, self.clear_start[1]]
            self.gcode.run_script_from_command('G90 \nG0 X%fY%fF%d'%(check_pos[0], check_pos[1], self.clear_speed))
            self.gcode.run_script_from_command('PROBE')
            self.gcode.run_script_from_command('SET_KINEMATIC_POSITION Z=0')

            #封嘴冷却至120
            self.gcode.run_script_from_command('SET_PIN PIN=fan0 VALUE=127.0')
            self.gcode.run_script_from_command('M109 S%f' %(self.closure_temp))
            self.gcode.run_script_from_command('M104 S0')
            self.gcode.run_script_from_command('SET_PIN PIN=fan0 VALUE=0.0')

            prtouch_v3.pres.tri_hold = [v for v in old_hold] # 恢复默认触发阈值
            self.gcode.respond_info(">>>old tri_hold = %s" % prtouch_v3.pres.tri_hold)

            self.gcode.run_script_from_command('G0 Z10 F300')  #擦完抬高回热床
            self.gcode.run_script_from_command('G0 X130Y130Z10 F6000')

            pass
        except Exception as e:
            self.gcode.respond_info(">>>NOZZLE_CLEAR ERROR: %s" % e)
            raise
        finally:
            self.inside_nozzle_clear= False


def load_config(config):
    return NozzleClear(config)