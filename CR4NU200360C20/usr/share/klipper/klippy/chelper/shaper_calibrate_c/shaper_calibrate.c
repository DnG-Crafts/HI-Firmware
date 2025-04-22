#include <stdint.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <getopt.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/ioctl.h>
#include <sys/stat.h>
#include <linux/types.h>
#include <stddef.h> 
#include <stdbool.h> 
#include <time.h>
#include "fftw3.h"
#include "shaper_calibrate.h"
#include "shaper_defs.h"
#ifndef __USE_MISC
#define __USE_MISC
#endif
#include <math.h>
#include "mem.h"
#ifdef CWCHELPER
#include "pyhelper.h"
#endif

const static double TEST_DAMPING_RATIOS[] = {
    0.075, 0.1, 0.15
};

const static char* AUTOTUNE_SHAPERS[] = {
    "zv",
    "mzv",
    "ei",
    "2hump_ei",
    "3hump_ei"
};

// todo 所有内存分配加上异常处理
// 需要返回的内存才用allocated分配，其余的都在栈上分配

// Function to find the lower bound index of x in arr.
// Returns the index of the first element in the range [first,last) which does not compare less than x.
size_t lower_bound(const double arr[], size_t size, double x) {
    size_t low = 0, high = size;
    while (low < high) {
        size_t mid = low + (high - low) / 2;
        if (arr[mid] < x) {
            low = mid + 1;
        } else {
            high = mid;
        }
    }
    return low;
}


// Linear interpolation function
double linearInterpolate(double x, const double xp[], const double fp[], size_t size) {
    double fp0, fp1, xp0, xp1;
    double slope;
    if (x <= xp[0]) {
        // x is below the interpolation range, linear extrapolation using the first two points
        // double slope = (fp[1] - fp[0]) / (xp[1] - xp[0]);
        // return fp[0] + slope * (x - xp[0]);
        fp0 = fp[0];
        fp1 = fp[1];
        xp0 = xp[0];
        xp1 = xp[1];
    } else if (x >= xp[size - 1]) {
        // x is above the interpolation range, linear extrapolation using the last two points
        // double slope = (fp[size - 1] - fp[size - 2]) / (xp[size - 1] - xp[size - 2]);
        // return fp[size - 1] + slope * (x - xp[size - 1]);
        fp0 = fp[size - 2];
        fp1 = fp[size - 1];
        xp0 = xp[size - 2];
        xp1 = xp[size - 1];
    } else {
        // x is within the interpolation range, perform linear interpolation
        size_t i = lower_bound(xp, size, x);
        // my_printf("lower bound is %d\n", i);
        if (i == 0) { // This case is handled to avoid underflow in the index calculation
            i = 1;
        }
        // double slope = (fp[i] - fp[i - 1]) / (xp[i] - xp[i - 1]);
        // return fp[i - 1] + slope * (x - xp[i - 1]);
        fp0 = fp[i - 1];
        fp1 = fp[i];
        xp0 = xp[i - 1];
        xp1 = xp[i];
    }
    // 如果xp1和xp0太接近了 就不进行插值
    if (fabs(xp1 - xp0) > 1e-7){
        slope = (fp1 - fp0) / (xp1 - xp0);
        return fp0 + slope * (x - xp0);
    }else {
        return (fp0 + fp1) / 2;
    }
}

void add_data(struct CalibrationData *this, struct CalibrationData *other){
    int joined_data_sets = this->data_sets + other->data_sets;    
    double* other_normalized = allocate_1d_array_double(this->size);
    if (!other_normalized) {
        my_perror("Memory allocation failed for normalize");
        exit(EXIT_FAILURE);
    }
    for (int i = 0; i < ARRAY_SIZE(this->_psd_list); i++){
        double* psd = this->_psd_list[i];
        double* other_psd = other->_psd_list[i];
        // double other_normalized[MAX_FREQ_BINS_LEN];
        // std::vector<double> other_normalized;
        for (int j = 0; j < this->size; j++){
            other_normalized[j] = linearInterpolate(this->freq_bins[j], other->freq_bins, other_psd, this->size);
        }
        for (int j = 0; j < this->size; j++){
            psd[j] = (psd[j] * this->data_sets + other_normalized[j] * other->data_sets) / joined_data_sets;
        }
    }
    free(other_normalized);
    this->data_sets = joined_data_sets;
}

/**
 * Normalizes the PSDs to the frequency bins.
*/
void normalize_to_frequencies(struct CalibrationData* data){
    for (int i = 0; i < ARRAY_SIZE(data->_psd_list); i++){
        double* psd = data->_psd_list[i];
        if (!psd) {
            my_perror("Memory allocation failed for _psd_list");
            exit(EXIT_FAILURE);
        };
        // my_printf("PSD: %p\n", psd);
        for (int j = 0; j < data->size; j++){
            psd[j] /= data->freq_bins[j] + 0.1; 
            if (data->freq_bins[j] < MIN_FREQ){
                psd[j] = 0.0;
            }
        }
    }
}

double* get_psd(struct CalibrationData* data, char* axis){
    for (int i = 0; i < ARRAY_SIZE(data->_psd_map); i++){
        if (strcmp(data->_psd_map[i].str, axis) == 0){
            return data->_psd_map[i].psd; 
        }    
    }
    return NULL;
}


double** _split_into_windows(const double* x, size_t x_size, int window_size, int overlap, int* out_n_windows) {
    int step_between_windows = window_size - overlap;
    *out_n_windows = (x_size - overlap) / step_between_windows;
    
    // 为窗口数组分配内存
    // double** windows = (double**)malloc(*out_n_windows * sizeof(double*));
    double** windows = allocate_2d_array_double(*out_n_windows, window_size);
    if (!windows) {
        my_perror("Memory allocation failed for windows");
        exit(EXIT_FAILURE);
    }

    for (int i = 0; i < *out_n_windows; ++i) {
        // 填充每个窗口的数据
        for (int j = 0; j < window_size; ++j) {
            int index = i * step_between_windows + j;
            if (index < x_size) {
                windows[i][j] = x[index];
            } else {
                // 如果源数组x的大小不足以填满当前窗口，则用0填充剩余部分
                windows[i][j] = 0.0;
            }
        }
    }

    return windows;
}

// 动态分配二维复数数组
fftw_complex** allocate_2d_array_fftw_complex(int rows, int cols) {
    fftw_complex** array = (fftw_complex**)malloc(rows * sizeof(fftw_complex*));
    if (!array) {
        my_perror("Memory allocation failed for fftw_complex** array");
        exit(EXIT_FAILURE);
    }
    for (int i = 0; i < rows; i++) {
        array[i] = (fftw_complex*)fftw_malloc(cols * sizeof(fftw_complex));
        if (!array[i]) {
            my_perror("Memory allocation failed for fftw_complex array");
            exit(EXIT_FAILURE);
        }
    }
    return array;
}

// 释放二维复数数组内存
void free_2d_array_fftw_complex(fftw_complex** array, int rows) {
    if (array) {
        for (int i = 0; i < rows; i++) {
            if(array[i]){
                fftw_free(array[i]);
                array[i] = NULL;
            }
        }
        free(array);
        array = NULL;
    }
}
// 释放窗口内存的函数
void free_windows(double** windows, int n_windows) {
    if (windows){
        for (int i = 0; i < n_windows; ++i) {
            if (windows[i]){
                free(windows[i]);
                windows[i] = NULL;
            }
        }
        free(windows);
        windows = NULL;
    }
}

// 示例释放结果内存的函数
void free_frequency_response(fftw_complex** result, int rows) {
    free_2d_array_fftw_complex(result, rows);
}

// 计算频率响应
fftw_complex** _calculate_frequency_response(double** windows, int rows, int nfft) {
    fftw_complex** result = allocate_2d_array_fftw_complex(rows, nfft);
    if (!result) {
        my_perror("Memory allocation failed for result array");
        exit(EXIT_FAILURE);
    }
    fftw_complex** windows_complex = allocate_2d_array_fftw_complex(rows, nfft);
    if (!windows_complex) {
        my_perror("Memory allocation failed for windows_complex array");
        exit(EXIT_FAILURE);
    }
    fftw_plan* plans = (fftw_plan*)malloc(rows * sizeof(fftw_plan));
    if (!plans) {
        my_perror("Memory allocation failed for fftw_plan array");
        exit(EXIT_FAILURE);
    }

    for (int i = 0; i < rows; i++) {
        for (int j = 0; j < nfft; ++j) {
            windows_complex[i][j][0] = windows[i][j]; // Real part
            windows_complex[i][j][1] = 0.0; // Imaginary part
        }
        plans[i] = fftw_plan_dft_1d(nfft, windows_complex[i], result[i], FFTW_FORWARD, FFTW_ESTIMATE);
    }

    // Execute FFT for each window
    for (int i = 0; i < rows; i++) {
        fftw_execute(plans[i]);
    }

    // Destroy FFTW plans
    for (int i = 0; i < rows; i++) {
        fftw_destroy_plan(plans[i]);
    }
    free(plans);
    free_2d_array_fftw_complex(windows_complex, rows);

    return result;
}

// 计算PSD
struct PSD _psd(double* x, int x_size, double fs, int nfft) {
    // double* window = allocate_1d_array_double(nfft); 
    double window[nfft];
    // if (!window) {
    //     my_perror("Memory allocation failed for window array");
    //     exit(EXIT_FAILURE);
    // }
    double scale = 0.0;
    double** windows = NULL; 
    fftw_complex** result = NULL; 
    // int windows_size; // 窗口数量
    int overlap = nfft / 2;
    int out_n_windows;
    struct PSD out;
    // Calculate window
    for (int i = 0; i < nfft; i++) {
        // 窗口是一个对称的尖峰形状，nfft此处是尖峰的宽度
        window[i] = tgamma(6.0) * pow(0.5 * (1.0 - cos(2.0 * M_PI * i / (nfft - 1))), 6.0);
        scale += pow(window[i], 2);
    }
    scale = 1.0 / scale;
    windows = _split_into_windows(x, x_size, nfft, overlap, &out_n_windows);
    // Apply windowing function and detrend
    for (int i = 0; i < out_n_windows; i++) {
        // 计算每个窗口的平均值
        double mean = 0;
        for (int j = 0; j < nfft; j++) {
            mean += windows[i][j]; 
        }
        mean /= nfft;
        for (int j = 0; j < nfft; j++) {
            // 去势加窗处理
            windows[i][j] = window[j] * (windows[i][j] - mean);
        }
    }
    // free(window);
    // window = NULL;

    // Compute PSD
    // result 和 windows一样的维度
    result = _calculate_frequency_response(windows, out_n_windows, nfft);
    free_2d_array_double(windows, out_n_windows);

    // 计算能量
    for (int i = 0; i < out_n_windows; i++) {
        for (int j = 0; j < nfft; j++) {
            result[i][j][0] = result[i][j][0] * result[i][j][0] + result[i][j][1] * result[i][j][1]; 
            result[i][j][0] *= 2 * scale / fs; 
        }
    }

    // 考虑直流分量和那奎斯特点
    int psd_size = nfft / 2 + 1;
    out.psd = allocate_1d_array_double(psd_size);
    if (!out.psd) {
        my_perror("Memory allocation failed for out.psd array");
        exit(EXIT_FAILURE);
    }
    // Welch's algorithm: average response over windows
    // 二维数组的列向求均值
    for (int i = 0; i < psd_size; i++) {
        double mean_real = 0.0;
        for (int j = 0; j < out_n_windows; j++) {
            mean_real += result[j][i][0];
        }
        out.psd[i] = (mean_real / out_n_windows);
    }
    free_2d_array_fftw_complex(result, out_n_windows);

    out.psd_size = psd_size;
    // 计算频率, fs是采样频率
    // nfft是采样率一半的向上取整2的n次幂，因此fs/nfft总是大于1的 
    // 所以freqs的间隔大于1
    // 傅氏变换对称计算又需要损失一半的宽度因此freqs的长度最多仅为采样率的1/4左右
    out.freqs = allocate_1d_array_double(psd_size);
    if (!out.freqs) {
        my_perror("Memory allocation failed for out.freqs array");
        exit(EXIT_FAILURE);
    }
    for (int i = 0; i < psd_size; i++) {
        out.freqs[i] = i * fs / nfft;
    }
    return out;
}

double* _get_column(double** raw_data, size_t rows, size_t cols, size_t col_index) {
    double* column;
    column= allocate_1d_array_double(rows); // (double*)malloc(rows * sizeof(double));
    if (!column) {
        my_perror("Memory allocation failed for column array");
        exit(EXIT_FAILURE);
    }
    for (size_t i = 0; i < rows; ++i) {
        column[i] = raw_data[i][col_index];
    }
    return column;
}

double* _add_vectors(const double* vec1, int size1, const double* vec2, int size2) {
    if (size1 != size2) {
        fprintf(stderr, "Vectors must be of the same size to add them.\n");
        return NULL;
    }
    double* result;
    result= allocate_1d_array_double(size1);
    if (!result) {
        my_perror("Memory allocation failed for result array");
        exit(EXIT_FAILURE);
    }
    for (size_t i = 0; i < size1; ++i) {
        result[i] = vec1[i] + vec2[i];
    }
    return result;
}
void init_calib_data_list_map(struct CalibrationData* data){
    if (data->psd_sum) {
        data->_psd_list[0] = data->psd_sum;    
    }
    if (data->psd_x) {
        data->_psd_list[1] = data->psd_x;
    }
    if (data->psd_y) {
        data->_psd_list[2] = data->psd_y;
    }
    if (data->psd_z) {
        data->_psd_list[3] = data->psd_z;
    }

    if (data->psd_sum) {
        data->_psd_map[0].str = "all";
        data->_psd_map[0].psd = data->psd_sum;
    }
    if (data->psd_x) {
        data->_psd_map[1].str = "x";
        data->_psd_map[1].psd = data->psd_x;
    }
    if (data->psd_y) {
        data->_psd_map[2].str = "y";
        data->_psd_map[2].psd = data->psd_y;
    }
    if (data->psd_z) {
        data->_psd_map[3].str = "z";
        data->_psd_map[3].psd = data->psd_z;
    }
}

struct CalibrationData calc_freq_response(double** raw_data, size_t rows, size_t cols) {
    int N = rows; // raw_data.size();
    double T = raw_data[rows - 1][0] - raw_data[0][0];
    double SAMPLING_FREQ= N / T;
    int M = 1 << (int)(log2(SAMPLING_FREQ * WINDOWN_T_SEC - 1) + 1);
    struct CalibrationData calibration_data = {
        .freq_bins = NULL,
        .psd_sum = NULL,
        .psd_x = NULL,
        .psd_y = NULL,
        .psd_z = NULL,
        .data_sets = 1,
        .size = 0
    };

    if (N <= M) {
        return calibration_data;
    }
    my_printf("Number of samples: %d \r\n", N);
    my_printf("Time duration: %f\r\n", T); 
    my_printf("Sampling frequency: %f\r\n", SAMPLING_FREQ);
    my_printf("Window size: %d\r\n", M);

    struct PSD fpx;
    struct PSD fpy;
    struct PSD fpz;
    double* raw_data_x = _get_column(raw_data, rows, cols, 1);
    double* raw_data_y = _get_column(raw_data, rows, cols, 2);
    double* raw_data_z = _get_column(raw_data, rows, cols, 3);

    fpx = _psd(raw_data_x, rows, SAMPLING_FREQ, M);
    fpy = _psd(raw_data_y, rows, SAMPLING_FREQ, M);
    fpz = _psd(raw_data_z, rows, SAMPLING_FREQ, M);
    
    free(raw_data_x);
    free(raw_data_y);
    free(raw_data_z);

    calibration_data.freq_bins = fpx.freqs;
    calibration_data.psd_x = fpx.psd;
    calibration_data.psd_y = fpy.psd;
    calibration_data.psd_z = fpz.psd; 
    // 没用到的freqs需要释放
    free(fpy.freqs);
    fpy.freqs = NULL;
    free(fpz.freqs);
    fpz.freqs = NULL;

    double* temp = allocate_1d_array_double(fpx.psd_size);
    if (!temp) {
        my_perror("Memory allocation failed for temp array");
        exit(EXIT_FAILURE);
    }
    for (int i = 0; i < fpx.psd_size; i++) {
        temp[i] = fpx.psd[i] + fpy.psd[i] + fpz.psd[i]; 
    }
    calibration_data.psd_sum = temp;
    calibration_data.size = fpx.psd_size;
    init_calib_data_list_map(&calibration_data);
    return calibration_data;
}

struct CalibrationData process_accelerometer_data(double** raw_data, size_t rows, size_t cols) {
    return calc_freq_response(raw_data, rows, cols);
}

void free_calibration_data(struct CalibrationData* data){
    if (data->freq_bins) {
        free(data->freq_bins);
        data->freq_bins = NULL;
    }
    if (data->psd_sum) {
        free(data->psd_sum);
        data->psd_sum = NULL;
    }
    if (data->psd_x) {
        free(data->psd_x);
        data->psd_x = NULL;
    }
    if (data->psd_y) {
        free(data->psd_y);
        data->psd_y = NULL;
    }
    if (data->psd_z) {
        free(data->psd_z);
        data->psd_z = NULL;
    }
}

/**
 * Estimates the shaper for a given test damping ratio and test frequencies.
 * 估计shaper的这一组脉冲的残余振动
 *  If the impulse sequence causes no vibration, then the
 *  convolution product will also cause no vibration
 * @param shaper The shaper object to estimate.
 * @param test_damping_ratio The damping ratio for the test.
 * @param test_freqs The frequencies for the test.
 *
 * @return A vector of doubles representing the estimated shaper values.
 * 返回的是残余振动百分比
 * @throws None
 */
double* _estimate_shaper(struct Shaper* shaper, double test_damping_ratio, double* test_freqs, int num_freqs) {
    double* result = allocate_1d_array_double(num_freqs);
    if (!result) {
        my_perror("Memory allocation failed for result array");
        exit(EXIT_FAILURE);
    }
    double* A = shaper->A;
    double* T = shaper->T; 
    double inv_D = 0;
    for (int i = 0; i < shaper->size; i++) {
       inv_D += A[i]; 
    }
    // 脉冲幅值归一化处理
    inv_D = 1.0 / inv_D;
    int n = shaper->size;
    // std::vector<double> result;
    // 残余振动的计算 见论文 http://code.eng.buffalo.edu/tdf/papers/acc_tut.pdf
    // 中的公式1
    // 把公式外部的指数部分放到了根号内部，演变成下面的公式
    // std::vector<double> test_freqs_test = {1, 3, 5, 7, 9};
    for (int i = 0; i < num_freqs; i++) {
        double omega = 2.0 * M_PI * test_freqs[i];
        double damping = test_damping_ratio * omega;
        double omega_d = omega * sqrt(1.0 - test_damping_ratio* test_damping_ratio);
        double sum_S = 0.0;
        double sum_C = 0.0;
        // 每个频点都计算响应
        // 参考graph_shaper.py中的estimate_shaper计算
        for (int i = 0; i < n; i++) {
            double W = A[i] * exp(-damping * (T[n - 1] - T[i]));
            sum_S += W * sin(omega_d * T[i]);
            sum_C += W * cos(omega_d * T[i]);
        }
        result[i] = sqrt(sum_S * sum_S + sum_C * sum_C) * inv_D;
    }
    return result;
}
struct EstimateResult _estimate_remaining_vibrations(struct Shaper *shaper, double test_damping_ratio, 
        double* freq_bins, double* psd, int size) {
    double* vals = _estimate_shaper(shaper, test_damping_ratio, freq_bins, size);
    
    // The input shaper can only reduce the amplitude of vibrations by
    // SHAPER_VIBRATION_REDUCTION times, so all vibrations below that
    // threshold can be ignored
    // Calculate the threshold by reducing the amplitude
    double vibr_threshold = 0;
    for (int i = 0; i < size; i++) {
        if (vibr_threshold < psd[i]){
            vibr_threshold = psd[i];
        }
    }
    vibr_threshold /= SHAPER_VIBRATION_REDUCTION;
    
    // Estimate remaining vibration energy
    double remaining_vibrations[size];
    for (int i = 0; i < size; i++) {
        remaining_vibrations[i] = fmax(vals[i] * psd[i] - vibr_threshold, 0.0);
    }
    // double remaining_sum = std::accumulate(remaining_vibrations.begin(), remaining_vibrations.end(), 0.0);
    // 所有频点上残余振动的累加
    double remaining_sum = 0.0;
    for (int i = 0; i < size; i++) {
        remaining_sum += remaining_vibrations[i];
    }
    // free(remaining_vibrations);

    // Energy sum above the threshold
    double all_vibrations[size];
    for (int i = 0; i < size; i++) {
        all_vibrations[i] = fmax(psd[i] - vibr_threshold, 0.0);
    }
    // double all_sum = std::accumulate(all_vibrations.begin(), all_vibrations.end(), 0.0);
    double all_sum = 0.0;
    for (int i = 0; i < size; i++) {
        all_sum += all_vibrations[i];
    }
    // free(all_vibrations);

    // Calculate the ratio of remaining energy
    struct EstimateResult res = {remaining_sum / all_sum, vals, size};
    return res;
}

double _get_shaper_smoothing(struct Shaper* shaper, double accel, double scv) {
    double half_accel = accel * 0.5;
    double* A = shaper->A;
    double* T = shaper->T;

    double inv_D = 0;
    for (int i = 0; i < shaper->size; i++) {
        inv_D += A[i];
    }
    inv_D = 1.0 / inv_D;

    int n = shaper->size;
    double ts = 0.0;
    for (int i = 0; i < n; i++) {
        ts += A[i] * T[i];
    }
    ts *= inv_D;

    double offset_90 = 0.0;
    double offset_180 = 0.0;
    for (int i = 0; i < n; i++) {
        if (T[i] >= ts) {
            offset_90 += A[i] * (scv + half_accel * (T[i] - ts)) * (T[i] - ts);
        }
        offset_180 += A[i] * half_accel * pow((T[i] - ts), 2);
    }
    offset_90 *= inv_D * sqrt(2.0);
    offset_180 *= inv_D;
    return fmax(offset_90, offset_180);
}

bool _is_double_equal(double a, double b, double eps) {
    return fabs(a - b) < eps;    
}

static bool _bitsect_func(double test_accel, struct Shaper* shaper) {
    const double TARGET_SMOOTHING = 0.12;
    return _get_shaper_smoothing(shaper, test_accel, 5.0) <= TARGET_SMOOTHING;
}

double _bisect(bool (*func)(double, struct Shaper*), struct Shaper* shaper) {
    double left = 1.0;
    double right = 1.0;
    // 寻找左边界
    while (!func(left, shaper)) {
        right = left;
        left *= 0.5;
    }
    // 寻找右边界
    if (_is_double_equal(left, right, 1e-10)) {
        while (func(right, shaper)) {
            right *= 2.0;
        }
    }
    // 二分
    while (right - left > 1e-8) {
        double middle = (left + right) * 0.5;
        if (func(middle, shaper)) {
            left = middle;
        } else {
            right = middle;
        }
    }
    return left;
}

double find_shaper_max_accel(struct Shaper* shaper) {
    double max_accel = _bisect(_bitsect_func, shaper);
    return max_accel;
}

struct CalibrationResult fit_shaper(struct ShaperConfig *shaper_cfg, struct CalibrationData *calibration_data, double max_smoothing) {
    // std::vector<double> test_freqs;
    // 测试点过多也会占用大量内存 优化的方向
    int test_freqs_size = (int)((MAX_SHAPER_FREQ - shaper_cfg->min_freq) / 0.2) + 1;
    double test_freqs[test_freqs_size];
    for (int i = 0; i < test_freqs_size; i++) {
        test_freqs[i] = shaper_cfg->min_freq + i * 0.2;
    }

    int freq_bins_size = calibration_data->size;
    // std::vector<double> freq_bins;
    // std::vector<double> psd;
    double freq_bins[(int)MAX_FREQ] = {0};
    double psd[(int)MAX_FREQ] = {0};
    // 筛选出频率范围内的数据
    int cnt = 0;
    for (int i = 0; i < freq_bins_size; i++) {
        if (calibration_data->freq_bins[i] <= MAX_FREQ) {
            // freq_bins.push_back(calibration_data.freq_bins[i]);
            // psd.push_back(calibration_data.psd_sum[i]);
            freq_bins[i] = calibration_data->freq_bins[i];
            psd[i] = calibration_data->psd_sum[i];
            cnt++;
        }
    }
    // 更新长度，经过筛选后，真正用到的长度
    calibration_data->size = cnt;
    freq_bins_size = cnt;

    // std::vector<double> psd_test = {
    //     0.00000000e+00, 0.00000000e+00, 0.00000000e+00, 0.00000000e+00,
    //     1.78198263e+02, 2.19975494e+02, 2.54748400e+02, 2.92461833e+02,
    //     3.23286552e+02, 3.54824801e+02, 4.03333436e+02, 4.88773661e+02,
    //     5.54660769e+02, 6.16919090e+02, 7.38900906e+02, 6.97048830e+02,
    //     7.19930061e+02, 8.00807703e+02, 9.86498362e+02, 1.03739777e+03,
    //     1.31996774e+03, 1.62674167e+03, 1.54741615e+03, 1.51569601e+03,
    //     1.44364200e+03, 1.44574608e+03, 1.53921883e+03, 1.78859585e+03,
    //     1.86731257e+03, 1.79329725e+03, 2.17940656e+03, 3.14780681e+03,
    //     4.08268389e+03, 5.08399767e+03, 9.79486072e+03, 1.35001878e+04,
    //     1.73919390e+04, 1.64533167e+04, 1.57411998e+04, 1.41801894e+04,
    //     1.45734506e+04, 1.59345679e+04, 1.47079810e+04, 1.29607711e+04,
    //     1.04490379e+04, 7.22698977e+03, 6.50931254e+03, 5.88800583e+03,
    //     5.40810142e+03, 4.57032193e+03, 3.73958999e+03, 3.66883155e+03,
    //     4.15770799e+03, 3.33244023e+03, 2.87956631e+03, 2.29590822e+03,
    //     1.93006283e+03, 2.49996486e+03, 1.82026114e+03, 1.22888485e+03,
    //     5.43452515e+02, 9.19670976e+01, 6.25151256e+01, 5.75950187e+01,
    //     4.87005914e+01, 4.88699261e+01, 5.04189689e+01, 5.22020419e+01,
    //     5.25316042e+01, 6.82924481e+01, 9.21505485e+01, 1.04600945e+02,
    //     1.28919507e+02, 9.94245677e+01, 5.52233894e+01, 5.32301965e+01,
    //     3.85172194e+01, 3.98955126e+01, 4.35683265e+01, 4.94997272e+01,
    //     6.46140178e+01, 5.79476039e+01, 6.89298759e+01, 7.35609839e+01,
    //     6.73043323e+01, 4.68707110e+01, 5.15107509e+01, 4.48360519e+01,
    //     3.43680159e+01, 2.98549187e+01, 3.37286627e+01, 2.84897609e+01,
    //     2.52261926e+01, 2.66257605e+01, 2.43287315e+01, 2.30522333e+01,
    //     2.14519772e+01, 2.07835225e+01, 2.05228335e+01, 1.40668891e+01,
    //     1.27649410e+01, 1.63917685e+01, 1.74473329e+01, 1.51241593e+01,
    //     1.22213622e+01, 9.74653931e+00, 1.04574347e+01, 9.19261376e+00,
    //     1.34200607e+01, 1.76649822e+01, 1.42252414e+01, 1.05918388e+01,
    //     1.17632757e+01, 1.01331467e+01, 8.03753150e+00, 7.14775555e+00,
    //     6.45883516e+00, 8.00572919e+00, 7.39320865e+00, 7.75840703e+00,
    //     7.77471025e+00, 8.07194795e+00, 8.02966145e+00, 1.39237990e+01,
    //     2.50361874e+01, 3.11597583e+01, 3.77081359e+01, 4.38510827e+01,
    //     3.10181312e+01, 4.27707681e+01, 4.38563141e+01, 3.75167854e+01,
    //     2.95180054e+01
    // };

    struct CalibrationResult best_res = {
        .name = "",
        .vibrs = 100.0, // 初始化为一个比较大的值
    };
    // 初始化为一个较大的值，方便后面比较
    // best_res.vibrs = max_smoothing + 0.1; // 为什么初始化为这个值？？
    struct CalibrationResult results[test_freqs_size];
    for (int i = 0; i < test_freqs_size; i++) {
        results[i].vals = NULL;
    }
    // 在freqbins上去遍历不同频率参数的shaper（阻尼比都默认一样），根据剩余震动，最大加速度，平滑度等评估shaper的性能
    // 从大往小遍历
    for (int i = test_freqs_size - 1; i >= 0; i--) {
        double test_freq = test_freqs[i];
        double shaper_vals[freq_bins_size]; // 不同频点参数的shaper在不同阻尼比上的最大值
        for (int j = 0; j < freq_bins_size; j++) {
            shaper_vals[j] = 0.0;
        }
        // 初始化一个shaper，用于评估计算
        struct Shaper shaper = shaper_cfg->init_func(test_freq, DEFAULT_DAMPING_RATIO);
        // 计算给定加速度下的smooth程度
        double shaper_smoothing = _get_shaper_smoothing(&shaper, 5000, 5.0);
        // 如果限制了最大的平滑系数
        // 计算shaper的平滑系数已经超过了最大的平滑系数
        // 并且best_res不为空，就直接返回，因为后面频率的降低，smoothing会越来越大
        if (max_smoothing > 1e-6 && shaper_smoothing > max_smoothing && strcmp(best_res.name, "")) {
            // 提前找到最优结果，释放不需要的内存 
            my_printf("i is %d, allocated vals number is %d\n", i, test_freqs_size - 1 - i);
            int cnt = 0;
            for (int j = test_freqs_size - 1; j > 0; j--) {
                if (results[j].vals && results[j].vals != best_res.vals) {
                    free(results[j].vals); 
                    results[j].vals = NULL;
                    cnt++;
                }
            }
            my_printf("fred mem is %d, best_res name: %s vals: %p\n", cnt, best_res.name, best_res.vals);
            return best_res;
        }
        // for (double dr : TEST_DAMPING_RATIOS) {
        int dr_len = ARRAY_SIZE(TEST_DAMPING_RATIOS);
        double shaper_vibrations = 0.0;
        // 计算不同阻尼比下的最大残余振动和振动百分比 
        for (int int_dr = 0; int_dr < dr_len; int_dr++) { 
            double vibrations;
            double* vals;
            struct EstimateResult res;
            double dr = TEST_DAMPING_RATIOS[int_dr];
            res = _estimate_remaining_vibrations(&shaper, dr, freq_bins, psd, freq_bins_size);
            vals = res.vals;
            vibrations = res.res_vibr;
            for (int j = 0; j < freq_bins_size; j++) {
                shaper_vals[j] = fmax(shaper_vals[j], vals[j]);
            }
            shaper_vibrations = fmax(shaper_vibrations, vibrations);
            free(res.vals);
        }
        // 计算当前shaper下满足指定smooth的最大加速度
        double max_accel = find_shaper_max_accel(&shaper);
        // 根据smooothing和最大残余振动百分比计算得出shaper的评分
        // score越低越好
        double shaper_score = shaper_smoothing * (pow(shaper_vibrations, 1.5) + shaper_vibrations * 0.2 + 0.01);
        struct CalibrationResult temp;
        temp.vals = allocate_1d_array_double(freq_bins_size);
        if (temp.vals == NULL) {
            my_perror("Memory allocation failed for temp.vals array");
            exit(EXIT_FAILURE);
        }
        temp.size = freq_bins_size;
        for (int j = 0; j < freq_bins_size; j++) {
            temp.vals[j] = shaper_vals[j];
        }
        temp.freq = test_freq;
        temp.name = shaper_cfg->name;
        temp.vibrs = shaper_vibrations;
        temp.smoothing = shaper_smoothing;
        temp.score = shaper_score;
        temp.max_accel = max_accel;
        results[i] = temp;
        // 根据振动百分比选择最优的shaper
        if (strcmp(best_res.name, "") == 0 || best_res.vibrs > results[i].vibrs) {
            best_res = results[i];
            // my_printf("best_res update name: %s vibrs: %f, best_res smoothing: %f\n", best_res.name, best_res.vibrs, best_res.smoothing);
        }
        // else if (strcmp(results[i].name, "zv") == 0) {
        //     my_printf("results[%d] name: %s vibrs: %f smoothing: %f\n", i, results[i].name, results[i].vibrs, results[i].smoothing);  
        // }
    }

    // ***************后面这部分大概率不会执行，优化的方向*****************
    // 可以results可以只是一个中间临时变量，不用分配内存

    // 初始化selected为振动最小的那个频点shaper
    struct CalibrationResult selected = best_res;
    // 遍历上面的结果，如果评分比较低，振动也高的不明显，就替换掉selected
    for (int i = test_freqs_size - 1; i >= 0; i--) {
        if (results[i].vibrs < best_res.vibrs * 1.1 && results[i].score < selected.score) {
            selected = results[i];
        }
    }
    // results存放了所有的结果，最后只需要返回一个，释放不需要的内存 
    for (int i = 0; i < test_freqs_size; i++) {
        if (results[i].vals && results[i].vals != selected.vals) {
           free(results[i].vals); 
           my_printf("name: %s free %p\n", results[i].name, results[i].vals);
           results[i].vals = NULL;
        } 
    }
    my_printf("selected: %s, vals: %p \n", selected.name, selected.vals);
    return selected;
}


// struct CalibrationResults{
//     struct CalibrationResult best_shaper;
//     struct CalibrationResults all_shapers[MAX_SHAPERS];
//     int all_shapers_size;
// };

static bool find_shaper_name(const char* shapers_names[], int shapers_names_size, char* name) {
    for (int i = 0; i < shapers_names_size; i++) {
        if (strcmp(shapers_names[i], name) == 0) {
            return true;
        }
    }
    return false;
}

// 横向比较各个shaper的评分和平滑度，选择最优的shaper
struct CalibrationResults find_best_shaper(struct CalibrationData *calibration_data, double max_smoothing) {
    // 这里指的是shaper的计算结果
    struct CalibrationResults res = {
        .best_shaper = {.name = "", .freq = 0.0, .vibrs = 0.0, .smoothing = 0.0, .score = 0.0, .max_accel = 0.0},
        .all_shapers = {},
        .all_shapers_size = 0
    };
    // 遍历每个shaper在shaper之间评估出最优的shaper
    for (int i = 0; i < MAX_SHAPERS; i++) {
        // 过滤掉不需要测试的shaper
        if (find_shaper_name(AUTOTUNE_SHAPERS, ARRAY_SIZE(AUTOTUNE_SHAPERS), INPUT_SHAPERS[i].name) == false) {
            continue;
        }
        // 寻找每个shaper的最优参数，评估维度包括振动百分比、平滑度等
        struct CalibrationResult shaper = fit_shaper(&INPUT_SHAPERS[i], calibration_data, max_smoothing);
        my_printf("shaper.name %s, shaper.freq %fHz, shaper.vibrs %f, shaper.smoothing %f, shaper.score %f, shaper.max_accel %f\n",\
                shaper.name, shaper.freq, shaper.vibrs, shaper.smoothing, shaper.score, shaper.max_accel);
        res.all_shapers[res.all_shapers_size++] = shaper;
        // score低，或者score不是很低，但是平滑度低，也可以选择为最优shaper
        if (!strcmp(res.best_shaper.name, "") || shaper.score * 1.2 < res.best_shaper.score || 
                (shaper.score * 1.05 < res.best_shaper.score && shaper.smoothing * 1.1 < res.best_shaper.smoothing)) {
            res.best_shaper = shaper;
        }
    }
    my_printf("best shaper.name %s, best shaper.freq %fHz, best shaper.vibrs %f, best shaper.smoothing %f, best shaper.score %f, best shaper.max_accel %f\n", \
    res.best_shaper.name, res.best_shaper.freq, res.best_shaper.vibrs, res.best_shaper.smoothing, res.best_shaper.score, res.best_shaper.max_accel);
    return res;
}

void free_calibrationresults(struct CalibrationResults* results) {
    for (int i = 0; i < results->all_shapers_size; i++) {
        if (results->all_shapers[i].vals){
            free(results->all_shapers[i].vals);
            results->all_shapers[i].vals = NULL;
        }
    }
}

void save_calibration_data(const char* output, const struct CalibrationData* calibration_data) {
    FILE* csvfile = fopen(output, "w");
    if (!csvfile) {
        fprintf(stderr, "Error opening file '%s'\n", output);
        exit(EXIT_FAILURE);
    }
    my_printf("output: %s\n", output);

    fprintf(csvfile, "freq,psd_x,psd_y,psd_z,psd_xyz\n");

    for (size_t i = 0; i < calibration_data->size; i++) {
        if (calibration_data->freq_bins[i] >= MAX_FREQ) {
            break;
        }
        fprintf(csvfile, "%f,%f,%f,%f,%f\n",
                calibration_data->freq_bins[i],
                calibration_data->psd_x[i],
                calibration_data->psd_y[i],
                calibration_data->psd_z[i],
                calibration_data->psd_sum[i]);
    }

    fclose(csvfile);
}

void remove_csv_suffix(char *str) {
    int len = strlen(str);
    const char *suffix = ".csv";
    int suffixLen = strlen(suffix);

    // 确保字符串长度大于后缀长度
    if (len > suffixLen) {
        // 比较末尾是否有".csv"后缀
        if (strcmp(str + len - suffixLen, suffix) == 0) {
            // 将".csv"后缀之前的字符设置为字符串终止符，从而去除后缀
            str[len - suffixLen] = '\0';
        }
    }
}

void save_calibration_res(const char* output_file, const char* name, const struct CalibrationData* calibration_data, struct CalibrationResults* calib_res)
{
    // 文件名加上时间戳
    // 获取当前时间戳
    time_t now = time(NULL);
    char timestamp[64];
    // 将时间戳转换为字符串
    strftime(timestamp, sizeof timestamp, "%Y-%m-%d-%H-%M-%S", localtime(&now));
    // 输出文件名
    char time_suffix[128] = {0};
    char file_name[256] = "/tmp/";
    strcat(file_name, output_file);
    sprintf(time_suffix, "-%s.csv", timestamp);
    remove_csv_suffix(file_name);
    strcat(file_name, "_");
    strcat(file_name, name);
    strcat(file_name, time_suffix);
    FILE* o_file = fopen(file_name, "w");
    
    if (o_file) {
        fprintf(o_file, "freq_bins, psd_sum, psd_x, psd_y, psd_z, after_shaper, zv_vibrs, mzv_vibrs, ei_vibrs, 2hump_ei_vibrs, 3hump_ei_vibrs\n");
        for (int i = 0; i < calib_res->best_shaper.size; i++) {
            fprintf(o_file, "%f, %f, %f, %f, %f, %f, ",
                    calibration_data->freq_bins[i],
                    calibration_data->psd_sum[i],
                    calibration_data->psd_x[i],
                    calibration_data->psd_y[i],
                    calibration_data->psd_z[i],
                    calib_res->best_shaper.vibrs * calibration_data->psd_sum[i]);
            
            for (int j = 0; j < calib_res->all_shapers_size; j++){
                fprintf(o_file, "%f, ", calib_res->all_shapers[j].vals[i] * 10000);
            }
            fprintf(o_file, "\n");
        }
        fclose(o_file);
    } else {
        my_printf("can't open file %s\n", file_name);
    }
}

