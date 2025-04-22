from . import tmc2208, tmc2130, tmc, tmc_uart
from os import remove
import time
import mcu

CML_ERR_CODE_X_AXIS_LINE_ERROR    = {'code':'key405', 'msg':'CHECK_MOTOR_LINE: X-axis motor line is not inserted', 'values':[]}
CML_ERR_CODE_Y_AXIS_LINE_ERROR    = {'code':'key406', 'msg':'CHECK_MOTOR_LINE: Y-axis motor line is not inserted', 'values':[]}
CML_ERR_CODE_Z_AXIS_LINE_ERROR    = {'code':'key407', 'msg':'CHECK_MOTOR_LINE: Z-axis motor line is not inserted', 'values':[]}
CML_ERR_CODE_Z1_AXIS_LINE_ERROR    = {'code':'key408', 'msg':'CHECK_MOTOR_LINE: Z1-axis motor line is not inserted', 'values':[]}

class TEST_TMC:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_command('READ_REG_TMC', self.cmd_read_reg, desc=self.cmd_READ_REG_help)
        self.gcode.register_command('CHECK_MOTOR_LINE', self.cmd_check_motor_line, desc=self.cmd_CHECK_MOTOR_LINE_help)
        self.gcode.register_command('CHECK_ZMOTOR_LINE', self.cmd_check_z_motor_line, desc=self.cmd_READ_REG_help)

    def ck_and_raise_error(self, err_code, vals=[]):  
        err_code['values'] = vals
        err_code['msg'] = 'Shutdown due to ' + err_code['msg']
        self.printer.invoke_shutdown(str(err_code))
        # while True:
        #     self.delay_s(1.)
        #     self.print_msg('RAISE_ERROR', str(err_code), True)
        raise self.printer.command_error(str(err_code))
        pass
    def delay_s(self, delay_s):
        toolhead = self.printer.lookup_object("toolhead")
        reactor = self.printer.get_reactor()
        eventtime = reactor.monotonic()
        if not self.printer.is_shutdown():
            toolhead.get_last_move_time()
            eventtime = reactor.pause(eventtime + delay_s)
            pass
    
    cmd_READ_REG_help = "Read tmc reg vals"
    def cmd_read_reg(self, gcmd):
        addr = gcmd.get_int('A', default = 0X6F, minval = 0, maxval = 0x7F) 
        stepper = gcmd.get('step',default = 'z')
        stepper_x_obj = self.printer.lookup_object('tmc2209 stepper_%s' % stepper)
        val = stepper_x_obj.mcu_tmc.test_get_register(addr)
        self.gcode.respond_info('tmc2209 stepper_%s reg val:'%stepper + hex(val))
        return val
        pass

    cmd_CHECK_MOTOR_LINE_help = "check motor line"
    def cmd_check_motor_line(self, gcmd):
        stepper = gcmd.get('STEP',default = 'z')
        self.gcode.run_script_from_command('FORCE_MOVE STEPPER=stepper_%s DISTANCE=0.5 VELOCITY=10'% stepper)
        self.delay_s(0.5)
        val = self.cmd_read_reg(gcmd)
        if((val & 0xff) != 0):
            self.delay_s(0.5)
            self.gcode.run_script_from_command('M84')
            if stepper == 'x':
                self.ck_and_raise_error(CML_ERR_CODE_X_AXIS_LINE_ERROR)
            elif stepper == 'y':
                self.ck_and_raise_error(CML_ERR_CODE_Y_AXIS_LINE_ERROR)
            else:
                self.ck_and_raise_error(CML_ERR_CODE_Z_AXIS_LINE_ERROR)
            pass
        self.gcode.run_script_from_command('FORCE_MOVE STEPPER=stepper_%s DISTANCE=-0.5 VELOCITY=10'% stepper)
        self.gcode.run_script_from_command('M84')
        self.gcode.respond_info('%s-axis motor line is inserted ok!!!!!' %stepper)
        pass

    cmd_CHECK_Z_MOTOR_LINE_help = "check z motor line"
    def cmd_check_z_motor_line(self, gcmd):
        self.gcode.run_script_from_command('FORCE_MOVE STEPPER=stepper_z DISTANCE=0.5 VELOCITY=10')
        self.gcode.run_script_from_command('FORCE_MOVE STEPPER=stepper_z1 DISTANCE=0.5 VELOCITY=10')
        self.delay_s(0.5)
        stepper_z_obj = self.printer.lookup_object('tmc2209 stepper_z')
        val = stepper_z_obj.mcu_tmc.test_get_register(111)
        self.gcode.respond_info('tmc2209 stepper_z reg val:'+ hex(val))
        if((val & 0xff) != 0):
            self.delay_s(0.5)
            self.gcode.run_script_from_command('M84')
            self.ck_and_raise_error(CML_ERR_CODE_Z_AXIS_LINE_ERROR)
            pass
        # 
        stepper_z1_obj = self.printer.lookup_object('tmc2209 stepper_z1')
        val = stepper_z1_obj.mcu_tmc.test_get_register(111)
        self.gcode.respond_info('tmc2209 stepper_z1 reg val:'+ hex(val))
        if((val & 0xff) != 0):
            self.delay_s(0.5)
            self.gcode.run_script_from_command('FORCE_MOVE STEPPER=stepper_z DISTANCE=-0.5 VELOCITY=10')
            self.gcode.run_script_from_command('M84')
            self.ck_and_raise_error(CML_ERR_CODE_Z1_AXIS_LINE_ERROR)
            pass
        self.delay_s(0.5)
        self.gcode.respond_info('Z-axis Z1-axis motor line is inserted ok!!!!!')
        self.gcode.run_script_from_command('FORCE_MOVE STEPPER=stepper_z DISTANCE=-0.5 VELOCITY=10')
        self.gcode.run_script_from_command('FORCE_MOVE STEPPER=stepper_z1 DISTANCE=-0.5 VELOCITY=10')
        self.gcode.run_script_from_command('M84')

        

def load_config(config):
    return TEST_TMC(config)