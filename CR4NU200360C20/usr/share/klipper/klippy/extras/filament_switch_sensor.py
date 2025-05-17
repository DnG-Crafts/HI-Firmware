# Generic Filament Sensor Module
#
# Copyright (C) 2019  Eric Callahan <arksine.code@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging

class RunoutHelper:
    def __init__(self, config):
        self.name = config.get_name().split()[-1]
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        # Read config
        self.runout_pause = config.getboolean('pause_on_runout', True)
        if self.runout_pause:
            self.printer.load_object(config, 'pause_resume')
        self.runout_gcode = self.insert_gcode = None
        gcode_macro = self.printer.load_object(config, 'gcode_macro')
        if self.runout_pause or config.get('runout_gcode', None) is not None:
            self.runout_gcode = gcode_macro.load_template(
                config, 'runout_gcode', '')
        if config.get('insert_gcode', None) is not None:
            self.insert_gcode = gcode_macro.load_template(
                config, 'insert_gcode')
        self.pause_delay = config.getfloat('pause_delay', .5, above=.0)
        self.event_delay = config.getfloat('event_delay', 3., above=0.)
        self.debounce_delay = config.getfloat('debounce_delay', 1., above=0.)
        # Internal state
        self.min_event_systime = self.reactor.NEVER
        self.filament_present = False
        self.filament_present_smooth = False
        self.inside_check_smooth = False
        self.sensor_enabled = True
        # Register commands and event handlers
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.gcode.register_mux_command(
            "QUERY_FILAMENT_SENSOR", "SENSOR", self.name,
            self.cmd_QUERY_FILAMENT_SENSOR,
            desc=self.cmd_QUERY_FILAMENT_SENSOR_help)
        self.gcode.register_mux_command(
            "SET_FILAMENT_SENSOR", "SENSOR", self.name,
            self.cmd_SET_FILAMENT_SENSOR,
            desc=self.cmd_SET_FILAMENT_SENSOR_help)
    def _handle_ready(self):
        self.min_event_systime = self.reactor.monotonic() + 2.
    def _runout_event_handler(self, eventtime):
        # Pausing from inside an event requires that the pause portion
        # of pause_resume execute immediately.
        pause_prefix = ""
        if self.runout_pause:
            pause_resume = self.printer.lookup_object('pause_resume')
            pause_resume.send_pause_command()
            pause_prefix = "PAUSE\n"
            self.printer.get_reactor().pause(eventtime + self.pause_delay)
        self._exec_gcode(pause_prefix, self.runout_gcode)
    def _insert_event_handler(self, eventtime):
        self._exec_gcode("", self.insert_gcode)
    def _exec_gcode(self, prefix, template):
        try:
            self.gcode.run_script(prefix + template.render() + "\nM400")
        except Exception:
            logging.exception("Script running error")
        self.min_event_systime = self.reactor.monotonic() + self.event_delay
    def note_filament_present(self, is_filament_present):
        def do_filament_work():
            self.filament_present = self.filament_present_smooth
            eventtime = self.reactor.monotonic()
            if eventtime < self.min_event_systime or not self.sensor_enabled:
                # do not process during the initialization time, duplicates,
                # during the event delay time, while an event is running, or
                # when the sensor is disabled
                logging.info(
                    "eventtime %.2f, self.min_event_systime %.2f, self.sensor_enabled %d" %
                    (eventtime, self.min_event_systime, self.sensor_enabled))
                return
            # Determine "printing" status
            idle_timeout = self.printer.lookup_object("idle_timeout")
            print_stats = self.printer.lookup_object('print_stats')
            is_printing = print_stats.state == "printing"
            # is_printing = idle_timeout.get_status(eventtime)["state"] == "Printing"
            # Perform filament action associated with status change (if any)
            logging.info("note_filament_present Stage2")
            if is_filament_present:
                if not is_printing and self.insert_gcode is not None:
                    # insert detected
                    self.min_event_systime = self.reactor.NEVER
                    logging.info(
                        "Filament Sensor %s: insert event detected, Time %.2f" %
                        (self.name, eventtime))
                    self.reactor.register_callback(self._insert_event_handler)
            elif is_printing and self.runout_gcode is not None:
                # runout detected
                self.min_event_systime = self.reactor.NEVER
                logging.info(
                    "Filament Sensor %s: runout event detected, Time %.2f" %
                    (self.name, eventtime))
                self.reactor.register_callback(self._runout_event_handler)

        def check_smooth(et=None):
            logging.info(f'XXXX1Filament Sensor {self.name},{is_filament_present}: filament not detected')
            self.reactor.pause(self.reactor.monotonic()+self.debounce_delay)
            if self.filament_present_smooth == 0:
                # logging.info(f'XXXX2Filament Sensor {self.name},{is_filament_present}: filament not detected')
                # self.inside_check_smooth = False
                # return
                logging.info(f'XXXX2Filament Sensor {self.name},{is_filament_present}: filament not detected')
                do_filament_work()
            self.inside_check_smooth = False

        logging.info("note_filament_present")
        if is_filament_present == self.filament_present_smooth:
            logging.info(f'XXXX3Filament Sensor {self.name},{is_filament_present}: filament not detected')
            return

        self.filament_present_smooth = is_filament_present
        if self.inside_check_smooth:
            logging.info(f'XXXX4 inside_check_smooth Filament Sensor {self.name},{is_filament_present}: filament not detected')
            return

        if self.name == "filament_sensor" and is_filament_present == 0:
            self.inside_check_smooth = True
            self.reactor.register_callback(check_smooth)
            return
        do_filament_work()

    def get_status(self, eventtime):
        return {
            "filament_detected": bool(self.filament_present),
            "enabled": bool(self.sensor_enabled)}
    cmd_QUERY_FILAMENT_SENSOR_help = "Query the status of the Filament Sensor"
    def cmd_QUERY_FILAMENT_SENSOR(self, gcmd):
        if self.filament_present:
            msg = "Filament Sensor %s: filament detected" % (self.name)
        else:
            msg = "Filament Sensor %s: filament not detected" % (self.name)
        gcmd.respond_info(msg)
    cmd_SET_FILAMENT_SENSOR_help = "Sets the filament sensor on/off"
    def cmd_SET_FILAMENT_SENSOR(self, gcmd):
        logging.info(f'Filament Sensor {self.name}: set enabled {gcmd.get_int("ENABLE", 1)}')
        self.sensor_enabled = gcmd.get_int("ENABLE", 1)

class SwitchSensor:
    def __init__(self, config):
        self.printer = printer = config.get_printer()
        buttons = printer.load_object(config, 'buttons')
        switch_pin = config.get('switch_pin')
        buttons.register_buttons([switch_pin], self._button_handler)
        self.runout_helper = RunoutHelper(config)
        self.get_status = self.runout_helper.get_status
    def _button_handler(self, eventtime, state):
        self.runout_helper.note_filament_present(state)
        if state:
            self.printer.send_event("box:extrude_process_stage7")

def load_config_prefix(config):
    return SwitchSensor(config)
