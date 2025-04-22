#ifndef __SHAPER_CALIBRATE__
#define __SHAPER_CALIBRATE__

#include "shaper_defs.h"

#define MIN_FREQ 5.
#define MAX_FREQ 200.
#define WINDOWN_T_SEC 0.5
#define MAX_SHAPER_FREQ 150
#define MAX_FREQ_BINS_LEN 512
struct str_vector_map 
{
    /* data */
    char* str;
    double* psd;
};

struct CalibrationData {
    double *freq_bins;
    double *psd_sum;
    double *psd_x;
    double *psd_y;
    double *psd_z;
    int size; // 实际数据的长度
    double* _psd_list[4];
    struct str_vector_map _psd_map[4];
    int data_sets;
};

struct ShperCfg {
    double min_freq;
    // void init_func(std::vector<double> &test_freqs, double dump_ratio);
    void (*init_func)(double* test_freq, double dump_ratio);
};

struct CalibrationResult 
{
    char* name;
    double freq;
    double* vals;
    int size;
    double vibrs;
    double smoothing;
    double score;
    double max_accel;
};


struct PSD {
    double* freqs;
    double* psd;
    int psd_size;
};

struct EstimateResult {
    double res_vibr;
    double *vals;    
    int size;
};


struct CalibrationResults {
    struct CalibrationResult best_shaper;
    struct CalibrationResult all_shapers[MAX_SHAPERS];
    int all_shapers_size;
};

struct ShaperCalibrate{
    struct Shaper best_shaper;
    struct Shaper all_shapers[MAX_SHAPERS];
};

struct CalibrationData process_accelerometer_data(double** raw_data, size_t rows, size_t cols);
void normalize_to_frequencies(struct CalibrationData* data);
struct CalibrationResults find_best_shaper(struct CalibrationData *calibration_data, double max_smoothing);
void free_calibration_data(struct CalibrationData* data);
void free_calibrationresults(struct CalibrationResults* results);
void save_calibration_data(const char* output, const struct CalibrationData* calibration_data);
void add_data(struct CalibrationData *this, struct CalibrationData *other);
void save_calibration_res(const char* output_file, const char* name, const struct CalibrationData* calibration_data, struct CalibrationResults* calib_res);
void remove_csv_suffix(char *str);
#endif