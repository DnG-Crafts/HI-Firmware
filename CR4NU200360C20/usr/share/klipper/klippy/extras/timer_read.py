import json
import logging


class TimerRead:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.print_stats = self.printer.lookup_object('print_stats')
        self.extruder = None
        self.heater_bed = None
        self.reactor = self.printer.get_reactor()
        self.interval = config.getfloat("interval", 1.)
        self.print_interval = config.getfloat("print_interval", 5.)
        self.extruder_interval = config.getfloat("extruder_interval", 1.)
        # tri_wave_ip = config.get('prtouch_v3', 'prth_dbg_ippt')
        self.tri_wave_ip = self.printer.lookup_object('prtouch_v3').dbg_ippt
        # READ_PRES
        self.gcode.register_command(
            "STAT_TIMER_READ", self.cmd_START_TIMER_READ)
        self.gcode.register_command(
            "STOP_TIMER_READ", self.cmd_STOP_TIMER_READ)
        self.gcode.register_command(
            "STAT_TEMP_TIMER_READ", self.cmd_START_TEMP_TIMER_READ)
        self.gcode.register_command(
            "STOP_TEMP_TIMER_READ", self.cmd_STOP_TEMP_TIMER_READ)
        self.read_pres_update_timer = self.reactor.register_timer(
            self.read_pres_update_event)
        self.read_extr_temp_timer = self.reactor.register_timer(self.read_extr_temp_event)
        self.printer.register_event_handler("klippy:ready", self.handle_ready)

    def cmd_START_TIMER_READ(self, gcmd):
        self.reactor.update_timer(self.read_pres_update_timer, self.reactor.NOW)

    def cmd_STOP_TIMER_READ(self, gcmd):
        self.reactor.update_timer(self.read_pres_update_timer,
                                  self.reactor.NEVER)

    def cmd_START_TEMP_TIMER_READ(self, gcmd):
        self.reactor.update_timer(self.read_extr_temp_timer, self.reactor.NOW)

    def cmd_STOP_TEMP_TIMER_READ(self, gcmd):
        self.reactor.update_timer(self.read_extr_temp_timer,
                                  self.reactor.NEVER)

    def read_extr_temp_event(self, eventtime):
        """读取喷嘴温度"""
        extr_status = self.extruder.get_status(eventtime)
        heater_status = self.heater_bed.get_status(eventtime)
        #  b'{"temperature": 28.39, "target": 0.0, "power": 0.0, "can_extrude": false, "pressure_advance": 0.08, "smooth_time": 0.04}'
        # 需要转换为
        # b'{"params":{"eventtime":82723.778140945,"status":{"heater_bed":{"temperature":22.85},"extruder":{"temperature":27.25}}}}'
        extr_temp = extr_status.get("temperature", 0.0)
        heater_temp = heater_status.get("temperature", 0.0)
        status = {
            "params": {"status": {"heater_bed": {"temperature": heater_temp}, "extruder": {"temperature": extr_temp}}}
        }
        # 上报服务器
        import threading
        t = threading.Thread(target=self.send_udp, args=(self.tri_wave_ip, json.dumps(status)))
        t.start()
        # self.send_udp(self.tri_wave_ip, json.dumps(status))
        return eventtime + self.extruder_interval

    def send_udp(self, tri_wave_ip, message):
        import socket

        # 创建UDP套接字
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 定义服务器地址和端口号
        # server_address = ('172.21.30.77', 12345)
        server_address = (tri_wave_ip, 12345)
        # message = b'This is the message.'

        try:
            # 发送数据到服务器
            logging.info('Timer read extr temperature Sending %s' % message)
            sent = sock.sendto(message.encode(), server_address)

            # 接收服务器的响应数据
            # print('Waiting to receive')
            # data, server = sock.recvfrom(4096)
            # print('Received %s' % data)
        except Exception as e:
            logging.error('Error: %s' % e)
            logging.exception(e)
        finally:
            logging.info('Closing socket')
            sock.close()

    def read_pres_update_event(self, eventtime):
        self.gcode.run_script_from_command("READ_PRES C=45")
        if self.print_stats.state == "printing":
            interval = self.print_interval
        else:
            interval = self.interval
        return eventtime + interval

    # Initialization
    def handle_ready(self):
        # Load printer objects
        # Start extrude factor update timer
        # wait 1s start
        # self.reactor.update_timer(self.read_pres_update_timer,
        #                           self.reactor.monotonic() + 1.)
        try:
            self.extruder = self.printer.lookup_object('extruder')
            self.heater_bed = self.printer.lookup_object('heater_bed')
        except Exception as e:
            logging.exception(e)


def load_config(config):
    return(TimerRead(config))


