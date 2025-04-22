import mcu, logging

class CommandError(Exception):
    pass

"""
[io_remap]
src_pin: PB0    # 输入pin脚索引号(被映射)
remap_pin: PA15  # 输出pin脚索引号(映射)
src_pullup: 1    # 输入pin脚的上下拉配置,1表示上拉(意味着读取到0表示触发),0表示下拉(意味着读取到1表示触发)
remap_def: 1     # 输出pin脚的默认输出电平
filterNum: 1     # 当读取输入pin脚有效电平持续时间大于等于filterNum * periodTicks, 置输出pin脚为有效电平状态。如果输入的参数为0, 将采用默认值5
periodTicks: 0  # 轮询输入pin脚周期, 单位ticks。如果输入的参数为0, 采用50uS对应的tick默认值
"""

class IORemap:
    error = CommandError
    def __init__(self, config):
        self.config = config
        self.printer = config.get_printer()
        self.src_pin = self.config.getsection('io_remap').get('src_pin')
        self.remap_pin = self.config.getsection('io_remap').get('remap_pin')
        self.src_pullup = self.config.getsection('io_remap').getint('src_pullup')
        self.remap_def = self.config.getsection('io_remap').getint('remap_def')
        self.filterNum = self.config.getsection('io_remap').getint('filterNum')
        self.periodTicks = self.config.getsection('io_remap').getint('periodTicks')
        # self.mcu = mcu.get_printer_mcu(self.printer, "mcu")
        self.mcu = mcu.get_printer_mcu(self.printer, "nozzle_mcu")
        # self.mcu = self.printer.lookup_object('mcu nozzle_mcu')
        self.oid = self.mcu.create_oid()
        self.mcu.register_config_callback(self._build_config)
        self.gcode = config.get_printer().lookup_object('gcode')
        self.gcode.register_command("SET_IOREMAP", self.cmd_SET_IOREMAP)

    def _build_config(self):       
        self.mcu.add_config_cmd("config_ioRemap oid=%d src_pin=%s src_pullup=%d remap_pin=%s remap_def=%d"
                                 % (self.oid,self.src_pin,self.src_pullup,self.remap_pin,self.remap_def))
    def cmd_SET_IOREMAP(self, gcmd):
        operation = gcmd.get_int('S', 0)
        # self.mcu.add_config_cmd("operation_ioRemap oid=%d operation=%d filterNum=%d periodTicks=%d" % 
                                # (self.oid, operation, self.filterNum, self.periodTicks))
        # "operation_ioRemap oid=%c sta=%c"
        operation_ioRemap = self.mcu.lookup_query_command("operation_ioRemap oid=%c operation=%c filterNum=%c periodTicks=%u",
                                                          "query_ioRemap oid=%c sta=%c", oid=self.oid)
        operation_ioRemap.send([self.oid, operation, self.filterNum, self.periodTicks])

def load_config(config):
    return IORemap(config)
