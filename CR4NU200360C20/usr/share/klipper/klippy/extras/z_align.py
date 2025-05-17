import mcu, logging

"""
[z_align]
quick_speed: 60 # mm/s  下降速度
slow_speed: 20 # mm/s  探测速度
rising_dist: 20 # mm  首次探测到光电后的上升距离
filter_cnt: 10 # 连续触发限位的次数，用作滤波
timeout: 30 # s 单次探测超时时间
retries: 5 # 重试次数
retry_tolerance: 10  # 两个光电的调整允许的最大偏差 10步 步距是0.0025mm
endstop_pin_z: PA15  # 光电触发
endstop_pin_z1: PA8  # 光电触发
zd_up: 0  # 步进电机远离限位开关的电平
zes_untrig: 1  # 限位开关未触发时的电平
diff_z_offset: 0.6 # 断电续打悬空差异补偿 压层时减小此值, 悬空时增大此值
"""
class CommandError(Exception):
    pass

class Zalign:
    error = CommandError
    def __init__(self, config):
        self.config = config
        self.printer = config.get_printer()
        self.full_steps_pre_rev = 200
        self.quickSpeed = self.config.getsection('z_align').getint('quick_speed')
        self.slowSpeed = self.config.getsection('z_align').getint('slow_speed')
        self.risingDist = self.config.getsection('z_align').getint('rising_dist')
        self.safe_rising = self.config.getsection('z_align').getint('safe_rising_dist')
        self.filterCnt = self.config.getsection('z_align').getint('filter_cnt')
        self.timeout = self.config.getsection('z_align').getint('timeout')
        self.retries = self.config.getsection('z_align').getint('retries')
        self.retry_tolerance = self.config.getsection('z_align').getint('retry_tolerance')
        self.endstop_pin_z = self.config.getsection('z_align').get('endstop_pin_z')                                       
        self.endstop_pin_z1 = self.config.getsection('z_align').get('endstop_pin_z1') 
        self.zd_up = self.config.getsection('z_align').getint('zd_up')
        self.zes_untrig = self.config.getsection('z_align').getint('zes_untrig')
        self.diff_z_offset = self.config.getsection('z_align').getfloat('diff_z_offset')
        self.mcu = mcu.get_printer_mcu(self.printer, "mcu")  
        self.oidz = self.mcu.create_oid()
        self.oidz1 = self.mcu.create_oid()
        self.mcu.register_config_callback(self._build_config)
        self.cur_retries = 0
        self.gcode = config.get_printer().lookup_object('gcode')
        self.gcode.register_command("ZDOWN", self.cmd_ZDOWN)
        self.gcode.register_command("ZDOWN_SWITCH", self.cmd_ZDOWN_SWITCH)
        self.zdown_switch_enable = 1
        self.gcode.register_command("UP_SAFE_Z", self.cmd_UP_SAFE_Z)

    def _build_config(self):  
        stepper_indx_z = 0
        stepper_indx_z1 = 1   
        step_pin_z = self.config.getsection('stepper_z').get('step_pin') 
        step_pin_z1 = self.config.getsection('stepper_z1').get('step_pin')    
        dir_pin_z = self.config.getsection('stepper_z').get('dir_pin') 
        dir_pin_z1 = self.config.getsection('stepper_z1').get('dir_pin')                                                                                                            

        config_z_align = "config_z_align oid=%d"%self.oidz
        config_z_align_add_z = "config_z_align_add oid=%d z_indx=%d zs_pin=%s" \
                                " zd_pin=%s zd_up=%d zes_pin=%s zes_untrig=%d" % (
                                    self.oidz, stepper_indx_z, step_pin_z, dir_pin_z, self.zd_up, self.endstop_pin_z, self.zes_untrig)
        config_z_align_add_z1 = "config_z_align_add oid=%d z_indx=%d zs_pin=%s" \
                                " zd_pin=%s zd_up=%d zes_pin=%s zes_untrig=%d" % (
                                    self.oidz, stepper_indx_z1, step_pin_z1, dir_pin_z1, self.zd_up, self.endstop_pin_z1, self.zes_untrig)
        logging.info(config_z_align)
        self.mcu.add_config_cmd(config_z_align)
        logging.info(config_z_align)
        self.mcu.add_config_cmd(config_z_align_add_z)
        logging.info(config_z_align)
        self.mcu.add_config_cmd(config_z_align_add_z1)

        config_z_align_up = "config_z_align_up oid=%d"%self.oidz1
        config_z_align_up_add_z = "config_z_align_up_add oid=%d z_indx=%d zs_pin=%s" \
                                " zd_pin=%s zd_up=%d zes_pin=%s zes_untrig=%d" % (
                                    self.oidz1, stepper_indx_z, step_pin_z, dir_pin_z, self.zd_up, self.endstop_pin_z, self.zes_untrig)
        config_z_align_up_add_z1 = "config_z_align_up_add oid=%d z_indx=%d zs_pin=%s" \
                                " zd_pin=%s zd_up=%d zes_pin=%s zes_untrig=%d" % (
                                    self.oidz1, stepper_indx_z1, step_pin_z1, dir_pin_z1, self.zd_up, self.endstop_pin_z1, self.zes_untrig)   
        logging.info(config_z_align_up)
        self.mcu.add_config_cmd(config_z_align_up)  
        logging.info(config_z_align_up)
        self.mcu.add_config_cmd(config_z_align_up_add_z)
        logging.info(config_z_align_up)
        self.mcu.add_config_cmd(config_z_align_up_add_z1)
    def cmd_ZDOWN_SWITCH(self, gcmd):
        self.zdown_switch_enable = gcmd.get_int('ENABLE', default=1)

    
    def cmd_UP_SAFE_Z(self, gcmd):
        self.gcode.respond_info("cmd_UP_SAFE_Z start")
        reactor = self.printer.get_reactor()
        #读取限位状态 避免限位开关异常下怼平台
        gcode = self.printer.lookup_object('gcode')
        fb1 = self.printer.lookup_object('filament_switch_sensor filament_sensor_4',None)
        fb2 = self.printer.lookup_object('filament_switch_sensor filament_sensor_5',None)
        if fb1 is not None:
            z1_limit_state = fb1.get_status(None).get("filament_detected")
        if fb2 is not None:
            z2_limit_state = fb2.get_status(None).get("filament_detected")
        if z1_limit_state and z2_limit_state:   #判断限位状态
            err_msg = """{"code":"key357", "msg":"光电开关状态异常或者是热床过于倾斜", "values":[]}"""
            raise gcode._respond_error(err_msg)

        query_z_align = self.mcu.lookup_query_command("query_z_align_up oid=%c enable=%c quickSpeed=%u slowSpeed=%u risingDist=%u filterCnt=%c",
                                                "z_align_status oid=%c flag=%i deltaError1=%i", oid=self.oidz1)    
        rotation_distance = self.config.getsection('stepper_z').getfloat('rotation_distance')  # 8
        microsteps = self.config.getsection('stepper_z').getfloat('microsteps')  # 16

        mcu_freq = self.mcu._serial.msgparser.get_constant_float('CLOCK_FREQ')
        subdivision = self.full_steps_pre_rev*microsteps # 200*16 = 3200
        step_distance = rotation_distance/subdivision # 8/3200 = 0.0025mm
        quickSpeedTicks = int(1/(self.quickSpeed/step_distance)*mcu_freq)
        slowSpeedTicks = int(1/(self.slowSpeed/step_distance)*mcu_freq)
        risingDistStep = int(self.safe_rising/step_distance)   #int(self.risingDist/step_distance)
        enable = 1

        #使能z轴
        toolhead = self.printer.lookup_object('toolhead')
        now_pos = toolhead.get_position()
        toolhead.set_position(now_pos, homing_axes=(2,))
        self.gcode.run_script_from_command("SET_STEPPER_ENABLE STEPPER=stepper_z ENABLE=1")
        self.gcode.run_script_from_command("SET_STEPPER_ENABLE STEPPER=stepper_z1 ENABLE=1")
        self.gcode.run_script_from_command('SET_KINEMATIC_POSITION Z=10')
        self.gcode.run_script_from_command("G91 \nG0 Z0.1 F600\n G90")
        self.gcode.run_script_from_command("M400")
        self.cur_retries = 0
        self.gcode.respond_info("START Z-UP")
        msg = "send query_z_align cur_retries:%s oid=%d enable=%d quickSpeed=%s slowSpeed=%s risingDist=%s filterCnt:%s"%(self.cur_retries, self.oidz1, enable, quickSpeedTicks, slowSpeedTicks, risingDistStep, self.filterCnt)
        params = query_z_align.send([self.oidz1, enable, quickSpeedTicks, slowSpeedTicks, risingDistStep, self.filterCnt])
        self.gcode.respond_info(msg)
        # {'oid': 1, 'flag': 0, 'deltaError1': 5, '#name': 'z_align_status', '#sent_time': 49.895344040666664, '#receive_time': 49.995911207}
        curtime = reactor.monotonic()
        reactor.pause(reactor.monotonic() + 1.0)
        while True:
            nowtime = reactor.monotonic()
            usetime = nowtime-curtime
            if usetime > self.timeout:
                self.gcode._respond_error("""{"code":"key351", "msg":"z_align ZDOWN timeout:%ss result: %s", "values":[]}"""%(self.timeout, str(self.mcu._serial.z_align_status)))
                return -10000
            if self.mcu._serial.z_align_status.get("flag", 0) == 1:
                self.gcode.respond_info("usetime:%s z_align_status :%s"%(usetime, str(self.mcu._serial.z_align_status)))
                deltaError = int(self.mcu._serial.z_align_status.get("deltaError1", 0))
                break
            reactor.pause(reactor.monotonic() + 0.1)
            return deltaError 
        self.gcode.respond_info("Z-UP END")
        self.gcode.run_script_from_command("SET_STEPPER_ENABLE STEPPER=stepper_z ENABLE=1")
        self.gcode.run_script_from_command("SET_STEPPER_ENABLE STEPPER=stepper_z1 ENABLE=1")

    def cmd_ZDOWN(self, gcmd):
        reactor = self.printer.get_reactor()
        self.heater_hot = self.printer.lookup_object('extruder').heater
        target_hot_temp_old = self.heater_hot.target_temp
        self.gcode.run_script_from_command("M104 S0")
        query_z_align = self.mcu.lookup_query_command("query_z_align oid=%c enable=%c quickSpeed=%u slowSpeed=%u risingDist=%u filterCnt=%c",
                                                      "z_align_status oid=%c flag=%i deltaError1=%i", oid=self.oidz)

        rotation_distance = self.config.getsection('stepper_z').getfloat('rotation_distance')  # 8
        microsteps = self.config.getsection('stepper_z').getfloat('microsteps')  # 16

        mcu_freq = self.mcu._serial.msgparser.get_constant_float('CLOCK_FREQ')
        subdivision = self.full_steps_pre_rev*microsteps # 200*16 = 3200
        step_distance = rotation_distance/subdivision # 8/3200 = 0.0025mm
        quickSpeedTicks = int(1/(self.quickSpeed/step_distance)*mcu_freq)
        slowSpeedTicks = int(1/(self.slowSpeed/step_distance)*mcu_freq)
        risingDistStep = int(self.risingDist/step_distance)
        enable = 1
        def run_cmd(cur_retries):
            deltaError = 0
            msg = "send query_z_align cur_retries:%s oid=%d enable=%d quickSpeed=%s slowSpeed=%s risingDist=%s filterCnt:%s"%(cur_retries, self.oidz, enable, quickSpeedTicks, slowSpeedTicks, risingDistStep, self.filterCnt)
            params = query_z_align.send([self.oidz, enable, quickSpeedTicks, slowSpeedTicks, risingDistStep, self.filterCnt])
            # {'oid': 1, 'flag': 0, 'deltaError1': 5, '#name': 'z_align_status', '#sent_time': 49.895344040666664, '#receive_time': 49.995911207}
            self.gcode.respond_info(msg)
            curtime = reactor.monotonic()
            reactor.pause(reactor.monotonic() + 1.0)
            while True:
                nowtime = reactor.monotonic()
                usetime = nowtime-curtime
                if usetime > self.timeout:
                    self.gcode._respond_error("""{"code":"key351", "msg":"z_align ZDOWN timeout:%ss result: %s", "values":[]}"""%(self.timeout, str(self.mcu._serial.z_align_status)))
                    return -10000
                if self.mcu._serial.z_align_status.get("flag", 0) == 1:
                    self.gcode.respond_info("usetime:%s z_align_status :%s"%(usetime, str(self.mcu._serial.z_align_status)))
                    deltaError = int(self.mcu._serial.z_align_status.get("deltaError1", 0))
                    break
                reactor.pause(reactor.monotonic() + 0.1)
            return deltaError
        toolhead = self.printer.lookup_object('toolhead')
        now_pos = toolhead.get_position()
        toolhead.set_position(now_pos, homing_axes=(2,))
        self.gcode.run_script_from_command("SET_STEPPER_ENABLE STEPPER=stepper_z ENABLE=1")
        self.gcode.run_script_from_command("SET_STEPPER_ENABLE STEPPER=stepper_z1 ENABLE=1")
        self.cur_retries = 0
        while True:
            if self.cur_retries < self.retries:
                deltaError = run_cmd(self.cur_retries)
            else:
                self.gcode._respond_error("""{"code":"key352", "msg":"z_align ZDOWN too many retries: %s, deltaError:%s retry_tolerance:%s", "values":[]}"""%(deltaError, self.retry_tolerance, str(self.retries)))
                break
            if deltaError == -10000:
                # timeout 
                toolhead = self.printer.lookup_object('toolhead')
                now_pos = toolhead.get_position()
                toolhead.set_position(now_pos, homing_axes=(0,1,2))
                gcmd = 'G1 F%d X%.3f Y%.3f Z%.3f' % (1000, now_pos[0]+0.001, now_pos[1], now_pos[2])
                self.gcode.run_script_from_command(gcmd)
                self.gcode.run_script_from_command("M84")
                break
            if abs(deltaError) < self.retry_tolerance:
                self.gcode.respond_info("ZDOWN end")
                break
            self.cur_retries += 1

        if toolhead.G29_flag == False:
            # 补偿0.2, 测试验证首层虚层的问题
            # offset_value = self.printer.lookup_object('virtual_sdcard').offset_value
            offset_value = 0
            now_pos = toolhead.get_position()
            real_zmax = self.read_real_zmax()
            # za = real_zmax + offset_value
            za = real_zmax
            # 在恢复双Z校准值前,先恢复设置Z轴最大高度值
            toolhead.set_position([now_pos[0], now_pos[1], za, now_pos[3]], homing_axes=(2,))
            logging.info("ZDOWN G29_flag is Fasle, real_zmax:%s offset_value:%s za:%s now_pos:%s" % (real_zmax, offset_value, za,str(now_pos)))
            self.gcode.run_script_from_command("G91\nG1 Z-10 F600\nG90")
            self.gcode.run_script_from_command("M400")
            self.gcode.run_script_from_command("ADJUST_STEPPERS")
            self.gcode.run_script_from_command("M400")
            now_pos = toolhead.get_position()
            logging.info("ZDOWN G29_flag is Fasle, after ADJUST_STEPPERS now_pos:%s"%str(now_pos))
        else:
            self.gcode.run_script_from_command("M400")
            toolhead = self.printer.lookup_object('toolhead')
            now_pos = toolhead.get_position()
            now_pos[2] = self.config.getsection('stepper_z').getfloat('position_max')
            toolhead.set_position(now_pos, homing_axes=(2,))
            logging.info("ZDOWN G29_flag is True, set zmax:%s" % str(now_pos))

        self.gcode.run_script_from_command("M104 S%d" %target_hot_temp_old)

        return 0

    def read_real_zmax(self):
        import os,json
        max_z = self.config.getsection('stepper_z').getfloat('position_max', default=360)
        logging.info("stepper_z position_max:%s" % max_z)
        data = max_z - 10
        if self.config.has_section("z_tilt"):
            z_tilt = self.printer.lookup_object('z_tilt')
            if os.path.exists(z_tilt.real_zmax_path):
                try:
                    with open(z_tilt.real_zmax_path, "r") as f:
                        data = json.loads(f.read()).get("zmax", 0)
                        if data > max_z:
                            data = max_z - 10
                except Exception as err:
                    logging.error(err)
        self.gcode.respond_info("real_zmax:%s"%data)
        return data



def load_config(config):
    return Zalign(config)
