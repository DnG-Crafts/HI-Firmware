# A utility class to test resonances of the printer
#
# Copyright (C) 2020  Dmitry Butyugin <dmbutyugin@google.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging, math, os, time
from . import shaper_calibrate
from subprocess import call
# import threading
import importlib
import chelper
import ctypes

# ROLL_CAL = 1

class TestAxis:
    def __init__(self, axis=None, vib_dir=None):
        if axis is None:
            self._name = "axis=%.3f,%.3f" % (vib_dir[0], vib_dir[1])
        else:
            self._name = axis
        if vib_dir is None:
            self._vib_dir = (1., 0.) if axis == 'x' else (0., 1.)
        else:
            s = math.sqrt(sum([d*d for d in vib_dir]))
            self._vib_dir = [d / s for d in vib_dir]
    def matches(self, chip_axis):
        if self._vib_dir[0] and 'x' in chip_axis:
            return True
        if self._vib_dir[1] and 'y' in chip_axis:
            return True
        return False
    def get_name(self):
        return self._name
    def get_point(self, l):
        return (self._vib_dir[0] * l, self._vib_dir[1] * l)

def _parse_axis(gcmd, raw_axis):
    if raw_axis is None:
        return None
    raw_axis = raw_axis.lower()
    if raw_axis in ['x', 'y']:
        return TestAxis(axis=raw_axis)
    dirs = raw_axis.split(',')
    if len(dirs) != 2:
        raise gcmd.error("""{"code": "key304", "msg": "Invalid format of axiss '%s'", "values":["%s"]}""" % (raw_axis,raw_axis))
    try:
        dir_x = float(dirs[0].strip())
        dir_y = float(dirs[1].strip())
    except:
        raise gcmd.error(
                """{"code": "key305", "msg": "Unable to parse axis direction '%s'", "values":["%s"]}""" % (raw_axis, raw_axis))
    return TestAxis(vib_dir=(dir_x, dir_y))

class VibrationPulseTest:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        # self.min_freq = config.getfloat('min_freq', 5., minval=1.)
        # # Defaults are such that max_freq * accel_per_hz == 10000 (max_accel)
        # self.max_freq = config.getfloat('max_freq', 10000. / 75.,
        #                                 minval=self.min_freq, maxval=200.)
        # 修改默认值范围
        self.min_freq = config.getfloat('min_freq', 5., minval=1.)
        self.max_freq = config.getfloat('max_freq', 90.,
                                        minval=self.min_freq, maxval=200.)
        self.accel_per_hz = config.getfloat('accel_per_hz', 75., above=0.)
        self.hz_per_sec = config.getfloat('hz_per_sec', 1.,
                                          minval=0.1, maxval=2.)

        self.probe_points = config.getlists('probe_points', seps=(',', '\n'),
                                            parser=float, count=3)
        # self.low_mem = config.getboolean('low_mem', True)
        # 检查 /usr/bin/calc_psd 文件是否存在
        calc_psd_exists = os.path.exists('/usr/bin/calc_psd')
        # 根据 /usr/bin/calc_psd 是否存在来设置 self.low_mem 的值
        self.low_mem = config.getboolean('low_mem', calc_psd_exists)
        try:
            self.numpy = importlib.import_module('numpy')
        except ImportError:
            raise self.error(
                    "Failed to import `numpy` module, make sure it was "
                    "installed via `~/klippy-env/bin/pip install` (refer to "
                    "docs/Measuring_Resonances.md for more details).")

    def get_start_test_points(self):
        return self.probe_points
    def prepare_test(self, gcmd):
        self.freq_start = gcmd.get_float("FREQ_START", self.min_freq, minval=1.)
        self.freq_end = gcmd.get_float("FREQ_END", self.max_freq,
                                       minval=self.freq_start, maxval=200.)
        self.hz_per_sec = gcmd.get_float("HZ_PER_SEC", self.hz_per_sec,
                                         above=0., maxval=2.)
    def run_test(self, axis, gcmd, helper, raw_values, calibration_data):
        toolhead = self.printer.lookup_object('toolhead')
        X, Y, Z, E = toolhead.get_position()
        sign = 1.
        freq = self.freq_start
        # Override maximum acceleration and acceleration to
        # deceleration based on the maximum test frequency
        systime = self.printer.get_reactor().monotonic()
        toolhead_info = toolhead.get_status(systime)
        old_max_accel = toolhead_info['max_accel']
        old_max_accel_to_decel = toolhead_info['max_accel_to_decel']
        max_accel = self.freq_end * self.accel_per_hz
        self.gcode.run_script_from_command(
                "SET_VELOCITY_LIMIT ACCEL=%.3f ACCEL_TO_DECEL=%.3f" % (
                    max_accel, max_accel))
        input_shaper = self.printer.lookup_object('input_shaper', None)
        if input_shaper is not None and not gcmd.get_int('INPUT_SHAPING', 0):
            input_shaper.disable_shaping()
            gcmd.respond_info("Disabled [input_shaper] for resonance testing")
        else:
            input_shaper = None
        gcmd.respond_info("Testing frequency %.0f Hz" % (freq,))
        while freq <= self.freq_end + 0.000001:
            # 周期的1/4作为运动时间
            t_seg = .25 / freq
            # 计算每个频点的加速度
            # 等效加速度？？
            accel = self.accel_per_hz * freq
            # 等效最大速度？
            max_v = accel * t_seg
            # 设置起始加速度
            toolhead.cmd_M204(self.gcode.create_gcode_command(
                "M204", "M204", {"S": accel}))
            # 计算运动长度 
            # 周期已经定了，加速度决定运动幅度
            # 加速度线性变化，整体L是在变小
            L = .5 * accel * t_seg**2
            # 根据长度计算xy的增量变化
            dX, dY = axis.get_point(L)
            # 计算目标位置
            # 最终给到运动规划的是目标位置
            nX = X + sign * dX
            nY = Y + sign * dY
            # 运动到最大振幅点
            # todo 如何告诉运动规划 运动这一步需要的时间呢？？
            # max_v作为底层速度规划的参考
            toolhead.move([nX, nY, Z, E], max_v)
            # 运动到原点 
            toolhead.move([X, Y, Z, E], max_v)
            # 运动完半个周期，开始反向
            sign = -sign
            old_freq = freq
            freq += 2. * t_seg * self.hz_per_sec
            # 频率增加到整数的时候打印一次
            if math.floor(freq) > math.floor(old_freq):
                gcmd.respond_info("Testing frequency %.0f Hz" % (freq,))
                if gcmd.get_int("ROLL_CAL", 1) == 1:
                    print("Testing frequency %.0f Hz" % (freq,))
                    # continue
                    self.printer.lookup_object('toolhead').wait_moves()
                    last_move_time = self.printer.lookup_object('toolhead').get_last_move_time() 
                    print('last_move_time is {}'.format(last_move_time))
                    # 更新本次采样结束时间
                    for chip_axis, aclient, chip_name in raw_values:
                        aclient.update_request_end_time(last_move_time)

                    before_exe_time = time.time()
                    for chip_axis, aclient, chip_name in raw_values:
                        # aclient.update_request_end_time(last_move_time)
                        if not aclient.has_valid_samples():
                            # aclient.update_request_start_time(current_time)
                            continue
                        ## use c function 
                        # struct CalibrationData process_accelerometer_data(double** raw_data, size_t rows, size_t cols)
                        samples = aclient.get_samples() 
                        logging.info("samples size {}".format(len(samples)))
                        data = self.numpy.array(samples)
                        # 创建一个指向double的指针的数组
                        ffi_main, ffi_lib = chelper.get_ffi()
                        # numpy convert to double** 
                        def call_process_accelerometer_data(raw_data_np):
                            # 确保numpy数组是正确的dtype
                            # raw_data_np = self.numpy.ascontiguousarray(raw_data_np, dtype=self.numpy.double)
                            # 获取行和列
                            rows, cols = raw_data_np.shape
                            logging.info("rows = %d, cols = %d" % (rows, cols))
                            raw_data_c = ffi_main.new("double *[]", rows)
                            # 将numpy数组中的每一行转换为一个C兼容的指针
                            row_data = [None] * rows
                            for i in range(rows):
                                row_data[i] = ffi_main.new("double []", cols) 
                                row_data[i][0] = raw_data_np[i][0]
                                row_data[i][1] = raw_data_np[i][1]
                                row_data[i][2] = raw_data_np[i][2]
                                row_data[i][3] = raw_data_np[i][3]
                                raw_data_c[i] = row_data[i]

                                # raw_data_c[i] = ffi_main.cast("double *", raw_data_np[i].ctypes.data)

                                # if i < 50:
                                #    logging.info("raw_data_c[{}] = {}, {}, {}, {}".format(i, raw_data_c[i][0], raw_data_c[i][1], raw_data_c[i][2], raw_data_c[i][3]))

                            # 调用C函数
                            result = ffi_lib.process_accelerometer_data(raw_data_c, rows, cols)
                            return result

                        result = call_process_accelerometer_data(data)
                        if calibration_data[axis] is None:
                            calibration_data[axis] = result 
                        else:
                            data = calibration_data[axis]
                            new_data = result
                            ffi_lib.add_data(ffi_main.addressof(data), ffi_main.addressof(new_data))
                            logging.info("data.data_sets is {}".format(data.data_sets))
                            # free the memory after added
                            ffi_lib.free_calibration_data(ffi_main.addressof(new_data))

                        aclient.cconn.msgs = []
                    # 更新下次采样开始时间 
                    exe_time = time.time() - before_exe_time
                    print("exe time is {}".format(exe_time))
                    for chip_axis, aclient, chip_name in raw_values:
                        aclient.update_request_start_time(last_move_time + exe_time)
                        print('requset start time is {}'.format(last_move_time + exe_time))

        # Restore the original acceleration values
        self.gcode.run_script_from_command(
                "SET_VELOCITY_LIMIT ACCEL=%.3f ACCEL_TO_DECEL=%.3f" % (
                    old_max_accel, old_max_accel_to_decel))
        # Restore input shaper if it was disabled for resonance testing
        if input_shaper is not None:
            input_shaper.enable_shaping()
            gcmd.respond_info("Re-enabled [input_shaper]")

class ResonanceTester:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.move_speed = config.getfloat('move_speed', 50., above=0.)
        self.test = VibrationPulseTest(config)
        if not config.get('accel_chip_x', None):
            self.accel_chip_names = [('xy', config.get('accel_chip').strip())]
        else:
            self.accel_chip_names = [
                ('x', config.get('accel_chip_x').strip()),
                ('y', config.get('accel_chip_y').strip())]
            if self.accel_chip_names[0][1] == self.accel_chip_names[1][1]:
                self.accel_chip_names = [('xy', self.accel_chip_names[0][1])]
        # 平滑度 影响振动测试的
        self.max_smoothing = config.getfloat('max_smoothing', None, minval=0.05)

        self.gcode = self.printer.lookup_object('gcode')
        # 类提供的命令方法
        self.gcode.register_command("MEASURE_AXES_NOISE",
                                    self.cmd_MEASURE_AXES_NOISE,
                                    desc=self.cmd_MEASURE_AXES_NOISE_help)
        self.gcode.register_command("TEST_RESONANCES",
                                    self.cmd_TEST_RESONANCES,
                                    desc=self.cmd_TEST_RESONANCES_help)
        self.gcode.register_command("SHAPER_CALIBRATE",
                                    self.cmd_SHAPER_CALIBRATE,
                                    desc=self.cmd_SHAPER_CALIBRATE_help)
        self.printer.register_event_handler("klippy:connect", self.connect)
        self.ffi_main, self.ffi_lib = chelper.get_ffi() 
        message = "Hello, C!".encode('utf-8')
        self.ffi_lib.resonance_tester_print_test(message)
        logging.info("%s" % (message)) 
        # result = self.ffi_lib.shaper_calibrate_test(0.3, b"testx", b"/root/Downloads/raw_data_x_20231228_120454.csv", b"./raw_calc_output.csv")   
        # logging.info("result is %d, shaper_calibrate_test finished" % (result)) 

    def connect(self):
        self.accel_chips = [
                (chip_axis, self.printer.lookup_object(chip_name))
                for chip_axis, chip_name in self.accel_chip_names]

    # test_point 可以传入测试起始的点，也可以从配置文件里面读取
    def _run_test(self, gcmd, axes, helper, raw_name_suffix=None,
                  accel_chips=None, test_point=None):
        toolhead = self.printer.lookup_object('toolhead')
        # 存放处理完后的数据
        calibration_data = {axis: None for axis in axes}

        self.test.prepare_test(gcmd)

        if test_point is not None:
            test_points = [test_point]
        else:
            test_points = self.test.get_start_test_points()

        for point in test_points:
            # todo manual_move和move有什么不同？？
            toolhead.manual_move(point, self.move_speed)
            if len(test_points) > 1 or test_point is not None:
                gcmd.respond_info(
                        "Probing point (%.3f, %.3f, %.3f)" % tuple(point))
            for axis in axes:
                toolhead.wait_moves()
                toolhead.dwell(0.500)
                if len(axes) > 1:
                    gcmd.respond_info("Testing axis %s" % axis.get_name())

                raw_values = []
                if accel_chips is None:
                    for chip_axis, chip in self.accel_chips:
                        # 寻找和当前轴匹配的加速度计
                        if axis.matches(chip_axis):
                            # 和下位机相关？？ 告诉下位机开始测量
                            aclient = chip.start_internal_client()
                            raw_values.append((chip_axis, aclient, chip.name))
                else:
                    for chip in accel_chips:
                        aclient = chip.start_internal_client()
                        raw_values.append((axis, aclient, chip.name))

                # Generate moves
                self.test.run_test(axis, gcmd, helper, raw_values, calibration_data)

                for chip_axis, aclient, chip_name in raw_values:
                    # 告诉下位机结束，更新结束时间
                    aclient.finish_measurements()
                    # 拼接名字后缀
                    if raw_name_suffix is not None:
                        # 拼接起始点和芯片名字
                        raw_name = self.get_filename(
                                'raw_data', raw_name_suffix, axis,
                                point if len(test_points) > 1 else None,
                                chip_name if accel_chips is not None else None,)
                        aclient.write_to_file(raw_name)
                        # 没看到打印此条消息？？
                        gcmd.respond_info(
                                "Writing raw accelerometer data to "
                                "%s file" % (raw_name,))
                if gcmd.get_int("ROLL_CAL", 1) == 0:
                    if helper is None:
                        continue
                    for chip_axis, aclient, chip_name in raw_values:
                        if not aclient.has_valid_samples():
                            raise gcmd.error(
						            """{"code":"key56", "msg":"accelerometer '%s' measured no data", "values": ["%s"]}""" % (
                                        chip_name, chip_name))
                        ## replace with c/cpp
                        if self.test.low_mem:
                            new_data = helper.lowmem_process_accelerometer_data(aclient)
                        else:
                            new_data = helper.process_accelerometer_data(aclient)
                        if calibration_data[axis] is None:
                            calibration_data[axis] = new_data
                        else:
                            calibration_data[axis].add_data(new_data)
                        ## replace with c/cpp end

        return calibration_data
    cmd_TEST_RESONANCES_help = ("Runs the resonance test for a specifed axis")
    def cmd_TEST_RESONANCES(self, gcmd):
        # Parse parameters
        axis = _parse_axis(gcmd, gcmd.get("AXIS").lower())
        # 可以指定芯片和测试点
        accel_chips = gcmd.get("CHIPS", None)
        test_point = gcmd.get("POINT", None)

        # 如果命令参数指定了测试点，则解析出坐标
        if test_point:
            test_coords = test_point.split(',')
            if len(test_coords) != 3:
                raise gcmd.error("Invalid POINT parameter, must be 'x,y,z'")
            try:
                test_point = [float(p.strip()) for p in test_coords]
            except ValueError:
                raise gcmd.error("Invalid POINT parameter, must be 'x,y,z'"
                " where x, y and z are valid floating point numbers")
        # 如果指定了芯片则解析出芯片型号
        if accel_chips:
            parsed_chips = []
            for chip_name in accel_chips.split(','):
                if "adxl345" in chip_name:
                    chip_lookup_name = chip_name.strip()
                else:
                    chip_lookup_name = "adxl345 " + chip_name.strip();
                chip = self.printer.lookup_object(chip_lookup_name)
                parsed_chips.append(chip)

        # 需要输出可以指定raw_data
        outputs = gcmd.get("OUTPUT", "resonances").lower().split(',')
        for output in outputs:
            if output not in ['resonances', 'raw_data']:
                raise gcmd.error("""{"code": "key306", "msg": "Unsupported output '%s', only 'resonances' and 'raw_data' are supported", "values":["%s"]}""" % (output, output))
        if not outputs:
            raise gcmd.error("""{"code": "key307", "msg": "No output specified, at least one of 'resonances' or 'raw_data' must be set in OUTPUT parameter", "values":[]}""")
        name_suffix = gcmd.get("NAME", time.strftime("%Y%m%d_%H%M%S"))
        if not self.is_valid_name_suffix(name_suffix):
            raise gcmd.error("""{"code":"key55", "msg":"Invalid NAME parameter", "values": []}""")
        # 共振结果输出，默认
        csv_output = 'resonances' in outputs
        # 原始数据输出
        raw_output = 'raw_data' in outputs

        # Setup calculation of resonances
        # 如果要输出计算结果
        if csv_output:
            # 共振计算器获取
            helper = shaper_calibrate.ShaperCalibrate(self.printer)
        else:
            helper = None

        data = self._run_test(
                gcmd, [axis], helper,
                raw_name_suffix=name_suffix if raw_output else None,
                accel_chips=parsed_chips if accel_chips else None,
                test_point=test_point)[axis]

        if gcmd.get_int("ROLL_CAL", 1) == 0:
            if csv_output:
                csv_name = self.save_calibration_data('resonances', name_suffix,
                                                    helper, axis, data,
                                                    point=test_point)
                gcmd.respond_info(
                        "Resonances data written to %s file" % (csv_name,))
        
        else:
            # for test
            self.ffi_lib.normalize_to_frequencies(self.ffi_main.addressof(data)) 
            # self.ffi_lib.save_calibration_data(b"/tmp/calib_data_py.csv", self.ffi_main.addressof(data))
            # 发送的对象必须能够被pickle，这样它们才能被序列化并在不同进程间传输。错误信息显示，_cffi_backend.__CDataOwn 对象不能被pickle
            # calib_res = helper.background_process_exec(self.ffi_lib.find_best_shaper, (self.ffi_main.addressof(data), 0.3))
            start_time = time.time()
            # print('before find_best_shaper time is {}'.format(time.time()))
            calib_res = self.ffi_lib.find_best_shaper(self.ffi_main.addressof(data), 0.3)
            end_time = time.time()
            output_file = b"raw_calc_output.csv"
            # print('after find_best_shaper time is {}'.format(time.time()))
            axis_name = axis.get_name()
            axis_name.encode("utf-8")
            self.ffi_lib.save_calibration_res(output_file, axis_name, self.ffi_main.addressof(data), self.ffi_main.addressof(calib_res))
            gcmd.respond_info(
                        "Resonances data written to %s file with c function, find_best_shaper exe time is %f" % (output_file, end_time - start_time))
            gcmd.respond_info("best shaper.name %s, best shaper.freq %fHz, best shaper.vibrs %f, best shaper.smoothing %f, best shaper.score %f, best shaper.max_accel %f\n" % \
                            (self.ffi_main.string(calib_res.best_shaper.name).decode("utf-8"), calib_res.best_shaper.freq, calib_res.best_shaper.vibrs, calib_res.best_shaper.smoothing, calib_res.best_shaper.score, calib_res.best_shaper.max_accel))
            self.ffi_lib.free_calibrationresults(self.ffi_main.addressof(calib_res))
            self.ffi_lib.free_calibration_data(self.ffi_main.addressof(data))

    cmd_SHAPER_CALIBRATE_help = (
        "Simular to TEST_RESONANCES but suggest input shaper config")
    def cmd_SHAPER_CALIBRATE(self, gcmd):
        # Parse parameters
        axis = gcmd.get("AXIS", None)
        copy_TestAxis_y_to_x = False
        if not axis:
            calibrate_axes = [TestAxis('x'), TestAxis('y')]
        # 检查小写的xy
        elif axis.lower() not in 'xy':
            raise gcmd.error("Unsupported axis '%s'" % (axis,))
        else:
            calibrate_axes = [TestAxis(axis.lower())]
            if axis.lower() == "y":
                copy_TestAxis_y_to_x = True

        max_smoothing = gcmd.get_float(
                "MAX_SMOOTHING", self.max_smoothing, minval=0.05)

        name_suffix = gcmd.get("NAME", time.strftime("%Y%m%d_%H%M%S"))
        if not self.is_valid_name_suffix(name_suffix):
            raise gcmd.error("Invalid NAME parameter")

        # Setup shaper calibration
        helper = shaper_calibrate.ShaperCalibrate(self.printer)

        calibration_data = self._run_test(gcmd, calibrate_axes, helper)

        configfile = self.printer.lookup_object('configfile')

        for axis in calibrate_axes:
            axis_name = axis.get_name()
            gcmd.respond_info(
                    "Calculating the best input shaper parameters for %s axis"
                    % (axis_name,))

            ## replace with c/cpp
            if gcmd.get_int("ROLL_CAL", 1) == 0:
                calibration_data[axis].normalize_to_frequencies()
                best_shaper, all_shapers = helper.find_best_shaper(
                        calibration_data[axis], max_smoothing, gcmd.respond_info)
                gcmd.respond_info(
                        "Recommended shaper_type_%s = %s, shaper_freq_%s = %.1f Hz"
                        % (axis_name, best_shaper.name,
                        axis_name, best_shaper.freq))

                helper.save_params(configfile, axis_name,
                                best_shaper.name, best_shaper.freq)
                csv_name = self.save_calibration_data(
                        'calibration_data', name_suffix, helper, axis,
                        calibration_data[axis], all_shapers)
                if copy_TestAxis_y_to_x:
                    helper.save_params(configfile, "x", best_shaper.name, best_shaper.freq)
                    csv_name_x = self.save_calibration_data('calibration_data', name_suffix, helper, TestAxis('x'), calibration_data[axis], all_shapers)
                    gcmd.respond_info("copy_TestAxis_y_to_x Recommended shaper_type_%s = %s, shaper_freq_%s = %.1f Hz" % ("x", best_shaper.name, "x", best_shaper.freq))
                    gcmd.respond_info("copy_TestAxis_y_to_x Shaper calibration data written to %s file" % (csv_name_x,))
                gcmd.respond_info(
                        "Shaper calibration data written to %s file" % (csv_name,))
            else:
                # gcmd.respond_info("debug mark 1")
                data = calibration_data[axis]
                self.ffi_lib.normalize_to_frequencies(self.ffi_main.addressof(data)) 
                # gcmd.respond_info("debug mark 2")
                # self.ffi_lib.save_calibration_data(b"/tmp/calib_data_py.csv", self.ffi_main.addressof(data))
                # 发送的对象必须能够被pickle，这样它们才能被序列化并在不同进程间传输。错误信息显示，_cffi_backend.__CDataOwn 对象不能被pickle
                # calib_res = helper.background_process_exec(self.ffi_lib.find_best_shaper, (self.ffi_main.addressof(data), 0.3))
                start_time = time.time()
                # print('before find_best_shaper time is {}'.format(time.time()))
                # gcmd.respond_info("debug mark 3")
                calib_res = self.ffi_lib.find_best_shaper(self.ffi_main.addressof(data), 0.3)
                end_time = time.time()
                output_file = b"shaper_calc_output.csv"
                print('after find_best_shaper time is {}'.format(time.time()))
                name = axis_name.encode('utf-8')

                # gcmd.respond_info("debug mark 4")
                self.ffi_lib.save_calibration_res(output_file, name, self.ffi_main.addressof(data), self.ffi_main.addressof(calib_res))
                # gcmd.respond_info(
                #             "Resonances data written to %s file with c function, find_best_shaper exe time is %f" % (output_file, end_time - start_time))
                gcmd.respond_info("best shaper.name %s, best shaper.freq %fHz, best shaper.vibrs %f, best shaper.smoothing %f, best shaper.score %f, best shaper.max_accel %f\n" % \
                                (self.ffi_main.string(calib_res.best_shaper.name).decode("utf-8"), calib_res.best_shaper.freq, calib_res.best_shaper.vibrs, calib_res.best_shaper.smoothing, calib_res.best_shaper.score, calib_res.best_shaper.max_accel))
                helper.save_params(configfile, axis_name,
                                self.ffi_main.string(calib_res.best_shaper.name).decode("utf-8"), calib_res.best_shaper.freq)
                # csv_name = self.save_calibration_data(
                #         'calibration_data', name_suffix, helper, axis,
                #         calibration_data[axis], all_shapers)
                if copy_TestAxis_y_to_x:
                    # gcmd.respond_info("debug mark 5")
                    helper.save_params(configfile, "x", self.ffi_main.string(calib_res.best_shaper.name).decode("utf-8"), calib_res.best_shaper.freq)
                    # gcmd.respond_info("debug mark 5.1")
                    # csv_name_x = self.save_calibration_data('calibration_data', name_suffix, helper, TestAxis('x'), calibration_data[axis], all_shapers)
                    # gcmd.respond_info("copy_TestAxis_y_to_x Recommended shaper_type_%s = %s, shaper_freq_%s = %.1f Hz" % ("x", self.ffi_main.string(calib_res.best_shaper.name).decode("utf-8"), "x", calib_res.calib_ressbest_shaper.freq))
                    # gcmd.respond_info("copy_TestAxis_y_to_x Recommended shaper_type_%s = %s" % ("x", self.ffi_main.string(calib_res.best_shaper.name).decode("utf-8")))
                    gcmd.respond_info("copy_TestAxis_y_to_x")
                    # gcmd.respond_info("debug mark 5.2")
                    # gcmd.respond_info("copy_TestAxis_y_to_x Shaper calibration data written to %s file" % (csv_name_x,))
                # gcmd.respond_info(
                #         "Shaper calibration data written to %s file" % (csv_name,))
                # gcmd.respond_info("debug mark 6")
                self.ffi_lib.free_calibrationresults(self.ffi_main.addressof(calib_res))
                self.ffi_lib.free_calibration_data(self.ffi_main.addressof(data))
                # gcmd.respond_info("debug mark 7")
                # todo 修改加速度为shaper参考值
            ## replace with c/cpp end

        gcode = self.printer.lookup_object('gcode')
        gcode.run_script_from_command("CXSAVE_CONFIG")
        call("sync", shell=True)
        # 保存到配置文件，并且使其立即生效
        input_shaper = self.printer.lookup_object("input_shaper", None)
        if not input_shaper:
            config = configfile.read_main_config()
            self.printer.reload_object(config, "input_shaper")
            gcode.run_script_from_command("UPDATE_INPUT_SHAPER")
            input_shaper = self.printer.lookup_object("input_shaper", None)
            input_shaper.enable_shaping()
        gcmd.respond_info(
            "The SAVE_CONFIG command will update the printer config file\n"
            "with these parameters and restart the printer.")

    cmd_MEASURE_AXES_NOISE_help = (
        "Measures noise of all enabled accelerometer chips")
    def cmd_MEASURE_AXES_NOISE(self, gcmd):
        meas_time = gcmd.get_float("MEAS_TIME", 2.)
        raw_values = [(chip_axis, chip.start_internal_client())
                      for chip_axis, chip in self.accel_chips]
        self.printer.lookup_object('toolhead').dwell(meas_time)
        for chip_axis, aclient in raw_values:
            aclient.finish_measurements()
        helper = shaper_calibrate.ShaperCalibrate(self.printer)
        for chip_axis, aclient in raw_values:
            if not aclient.has_valid_samples():
                raise gcmd.error(
                        "%s-axis accelerometer measured no data" % (
                            chip_axis,))
            data = helper.process_accelerometer_data(aclient)
            vx = data.psd_x.mean()
            vy = data.psd_y.mean()
            vz = data.psd_z.mean()
            gcmd.respond_info("Axes noise for %s-axis accelerometer: "
                              "%.6f (x), %.6f (y), %.6f (z)" % (
                                  chip_axis, vx, vy, vz))

    def is_valid_name_suffix(self, name_suffix):
        return name_suffix.replace('-', '').replace('_', '').isalnum()

    def get_filename(self, base, name_suffix, axis=None,
                     point=None, chip_name=None):
        name = base
        if axis:
            name += '_' + axis.get_name()
        if chip_name:
            name += '_' + chip_name.replace(" ", "_")
        if point:
            name += "_%.3f_%.3f_%.3f" % (point[0], point[1], point[2])
        name += '_' + name_suffix
        return os.path.join("/tmp", name + ".csv")

    def save_calibration_data(self, base_name, name_suffix, shaper_calibrate,
                              axis, calibration_data,
                              all_shapers=None, point=None):
        output = self.get_filename(base_name, name_suffix, axis, point)
        shaper_calibrate.save_calibration_data(output, calibration_data,
                                               all_shapers)
        return output

def load_config(config):
    return ResonanceTester(config)
