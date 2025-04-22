import logging

class ExternalMaterialWrapper():
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        not_pin = config.get("not_pin", None)
        self.addr = config.getint("addr", default=0x11)
        buttons = self.printer.load_object(config, "buttons")
        self._serial = None
        self.printer.register_event_handler("klippy:ready", self.find_objs)
        self.gcode.register_command("EXTERNAL_MATERIAL", self.cmd_external_material)
        if not_pin:
            logging.info("not_pin: %s" % not_pin)
            buttons.register_buttons([not_pin], self._button_handler)
        else:
            logging.warning("do not define not_pin")
        self.external_material_data = {
            "vender": "-1",
            "color_value": "-1",
            "material_type": "-1",
        }

    def find_objs(self):
        self._serial = self.printer.lookup_object("serial_485 " + "serial485")

    def _button_handler(self, eventtime, state):
        logging.info("not_pin trigger, state: %s" % state)
        if state:
            self.reactor.register_callback(self.send_data)

    def send_data(self, eventtime):
        cmd = b'\x02' # byte string
        addr = b'\x11'
        timeout = 0.5
        state = b'\xff'
        length = b'\x03' # state + cmd + crc
        data_send = addr + length + state + cmd
        send_data_string = ' '.join(hex(byte) for byte in data_send)
        logging.info("zdata_send: %s" % send_data_string)
        ret = self._serial.cmd_send_data_with_response(data_send, timeout)
        if ret is None:
            logging.warning("do not get respond")
            return
        else:
            rfid = ''.join(chr(num) for num in ret[5:-1])
            if len(rfid) != 40:
                logging.warning("rfid[%s] is error" % rfid)
            else:
                logging.info("rfid: %s" % rfid)
                self.external_material_data["vender"] = rfid
                self.external_material_data["material_type"] = rfid[11:17]
                self.external_material_data["color_value"] = rfid[17:24]

    def cmd_external_material(self, gcmd):
        cmd = b'\x02' # byte string
        addr = b'\x11'
        timeout = 0.5
        self.send_data(timeout)

    def get_status(self, eventtime):
        return self.external_material_data