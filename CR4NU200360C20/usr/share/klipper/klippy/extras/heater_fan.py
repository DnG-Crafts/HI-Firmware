# Support fans that are enabled when a heater is on
#
# Copyright (C) 2016-2020  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
from . import fan

PIN_MIN_TIME = 0.100

class PrinterHeaterFan:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.printer.load_object(config, 'heaters')
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        self.heater_names = config.getlist("heater", ("extruder",))
        self.heater_temp = config.getfloat("heater_temp", 50.0)
        self.heaters = []
        self.fan = fan.Fan(config, default_shutdown_speed=1.)
        self.fan_speed = config.getfloat("fan_speed", 1., minval=0., maxval=1.)
        self.last_speed = 0.
        # 解析温度-速度映射（如果存在）
        temp_speed_str = config.get("temp_speed_map", None)
        self.temp_speed_map = None
        if temp_speed_str:
            self.temp_speed_map = {}
            for pair in temp_speed_str.split(','):
                temp, speed = pair.split(':')
                self.temp_speed_map[float(temp)] = float(speed)
    def handle_ready(self):
        pheaters = self.printer.lookup_object('heaters')
        self.heaters = [pheaters.lookup_heater(n) for n in self.heater_names]
        reactor = self.printer.get_reactor()
        reactor.register_timer(self.callback, reactor.monotonic()+PIN_MIN_TIME)
    def get_status(self, eventtime):
        return self.fan.get_status(eventtime)
    def callback(self, eventtime):
        speed = 0.
        if self.temp_speed_map:
            max_temp = 0
            for heater in self.heaters:
                current_temp, target_temp = heater.get_temp(eventtime)
                if target_temp or current_temp > self.heater_temp:
                    speed = min(self.temp_speed_map.values())
                    if current_temp > max_temp:
                        max_temp = current_temp

            # 根据最大温度查找对应的风扇速度
            for temp in sorted(self.temp_speed_map.keys(), reverse=True):
                if max_temp >= temp:
                    speed = self.temp_speed_map[temp]
                    break
        else:
            # 保持原来的逻辑
            for heater in self.heaters:
                current_temp, target_temp = heater.get_temp(eventtime)
                if target_temp or current_temp > self.heater_temp:
                    speed = self.fan_speed
        if speed != self.last_speed:
            self.last_speed = speed
            curtime = self.printer.get_reactor().monotonic()
            print_time = self.fan.get_mcu().estimated_print_time(curtime)
            self.fan.set_speed(print_time + PIN_MIN_TIME, speed)
        return eventtime + 1.

def load_config_prefix(config):
    return PrinterHeaterFan(config)
