import logging


class FanFeedback:
    def __init__(self, config):
        self.printer = config.get_printer()

        self.print_delay_time = config.getfloat('print_delay_time', 5.)
        self.current_delay_time = config.getfloat('current_delay_time', 2.)
        self.gcode = config.get_printer().lookup_object('gcode')

        ppins = self.printer.lookup_object('pins')

        self.params = []
        sensor_pin = []
        pin_params = []
        fan_num = 0
        self.config_cmd = None
        for i in range(0, 5):
            sensor_pin.append(config.get("fan%d_pin" % i, None))
            # logging.info("fan feedback sensor_pin: %s" % sensor_pin)
            if not sensor_pin[i]:
                continue
            fan_num += 1
            pin_params.append(ppins.lookup_pin(sensor_pin[i], can_invert=False, can_pullup=True))
        mcu = pin_params[0]['chip']
        oid = mcu.create_oid()
        if fan_num > 0:
            fan_num = fan_num - 1
            self.config_cmd = "config_fancheck oid=%d fan_num=%d fan0_pin=%s pull_up0=%s" \
                            " fan1_pin=%s pull_up1=%s fan2_pin=%s pull_up2=%s fan3_pin=%s" \
                            " pull_up3=%s fan4_pin=%s pull_up4=%s" % (
                oid, fan_num + 1,
                pin_params[0]['pin'], pin_params[0]["pullup"],
                pin_params[1 if 1 < fan_num else fan_num]['pin'], pin_params[1 if 1 < fan_num else fan_num]["pullup"],
                pin_params[2 if 2 < fan_num else fan_num]['pin'], pin_params[2 if 2 < fan_num else fan_num]["pullup"],
                pin_params[3 if 3 < fan_num else fan_num]['pin'], pin_params[3 if 3 < fan_num else fan_num]["pullup"],
                pin_params[4 if 4 < fan_num else fan_num]['pin'], pin_params[4 if 4 < fan_num else fan_num]["pullup"]
            )
        # self.gcode.respond_info("config_cmd: %s"%(str(config_cmd)))
        mcu.register_response(self._handle_result_fan_check0, "fan_status", oid)
        param = i, self.config_cmd, pin_params, mcu, oid
        # logging.info("%s" % (config_cmd))
        mcu.add_config_cmd(self.config_cmd)
        self.params.append(param)
        self.which_fan = 2**(fan_num+1) - 1
        self.fan_num = fan_num

        
        self.gcode.register_command("QUERY_FAN_CHECK", self.cmd_QUERY_FAN_CHECK, desc=self.cmd_QUERY_FAN_CHECK_help)
        self.print_stats = self.printer.load_object(config, 'print_stats')
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        self.cx_fan_status = {}
        webhooks = self.printer.lookup_object('webhooks')
        webhooks.register_endpoint("get_cx_fan_status",
                                   self._get_cx_fan_status)

    def handle_ready(self):
        reactor = self.printer.get_reactor()
        reactor.register_timer(
            self.cx_fan_status_update_event, reactor.monotonic()+1.)

    def delay_s(self, delay_s):
        toolhead = self.printer.lookup_object("toolhead")
        reactor = self.printer.get_reactor()
        eventtime = reactor.monotonic()
        if not self.printer.is_shutdown():
            toolhead.get_last_move_time()
            eventtime = reactor.pause(eventtime + delay_s)
            pass

    def _get_cx_fan_status(self):
        return self.cx_fan_status

    def cx_fan_status_update_event(self, eventtime):
        if self.print_stats.get_status(eventtime).get("state") != "printing":
            next_time = eventtime + self.current_delay_time
        else:
            next_time = eventtime + self.print_delay_time
        for i in self.params:
            cmd = "query_fancheck oid=%c which_fan=%c"
            oid = i[4]
            mcu = i[3]
            query_cmd = mcu.lookup_command(cmd, cq=None)
            # log_cmd = "query_fancheck oid=%s which_fan=%s" % (oid, 31)
            # logging.info("%s" % log_cmd)
            # query_cmd.send([oid, self.which_fan])
            query_cmd.send([oid, self.which_fan])
        return next_time

    cmd_QUERY_FAN_CHECK_help = "Check CXSW Special Fan Status"
    def cmd_QUERY_FAN_CHECK(self, gcmd):
        self.gcode.respond_info("config_cmd: %s"%(str(self.config_cmd)))
        self.gcode.respond_info("%s" % self.cx_fan_status)

    def _handle_result_fan_check0(self, params):
        # logging.info("_handle_result_fan_check0: %s" % params)
        # self.cx_fan_status["fan0_speed"] = params.get("fan0_speed", 0)
        # self.gcode.respond_info("fan_check0  %s"%(str(params)))
        self.cx_fan_status = {
            "fan0_speed": params.get("fan0_speed", 0),
            "fan1_speed": params.get("fan1_speed", 0),
            "fan2_speed": params.get("fan2_speed", 0),
            "fan3_speed": params.get("fan3_speed", 0),
            "fan4_speed": params.get("fan4_speed", 0),
        }

    def _handle_result_fan_check1(self, params):
        # logging.info("_handle_result_fan_check1: %s" % params)
        # self.cx_fan_status["fan1_speed"] = params.get("fan1_speed", 0)
        # self.gcode.respond_info("fan_check1 %s"%(str(params)))
        self.cx_fan_status = {
            "fan0_speed": self.cx_fan_status.get("fan0_speed", 0),
            "fan1_speed": params.get("fan1_speed", 0),
            "fan2_speed": self.cx_fan_status.get("fan2_speed", 0),
            "fan3_speed": self.cx_fan_status.get("fan3_speed", 0),
            "fan4_speed": self.cx_fan_status.get("fan4_speed", 0),
        }

    def get_status(self, eventtime):
        return self.cx_fan_status

def load_config(config):
    return FanFeedback(config)