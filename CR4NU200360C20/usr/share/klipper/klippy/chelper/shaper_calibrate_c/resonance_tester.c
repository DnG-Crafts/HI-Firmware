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
#include <time.h>
#include "shaper_calibrate.h"
#include "mem.h"
#ifdef CWCHELPER
#include "pyhelper.h"
#endif

size_t estimate_memory_usage(double** data, int rows, int cols) {
    // size_t totalSize = sizeof(data); // 内存开销，包括vector的内部指针等
    size_t totalSize = sizeof(double) * rows * cols; // double * rows * cols;
    // for (const auto& row : data) {
    // for (int i = 0; i < rows; i++) {
    //     totalSize += sizeof(row); // 每一行的vector对象开销
    //     totalSize += row.capacity() * sizeof(float); // 实际存储数据所用的内存
    // }
    return totalSize;
}


/**
 * params: [AXIS=<axis>] [NAME=<name>] [FREQ_START=<min_freq>] [FREQ_END=<max_freq>]
 *         [HZ_PER_SEC=<hz_per_sec>] [CHIPS=<adxl345_chip_name>] [MAX_SMOOTHING=<max_smoothing>]
 */
// int main(int argc, char *argv[]) {
//     // Definitions for calibration parameters
//     char* axis = "X";
//     char name[32] = "default";
//     char* adxl345_chip_name = "ADXL345";
//     int min_freq = 0;
//     int max_freq = 0;
//     int hz_per_sec = 0;
//     float max_smoothing = 0.0f;
//     char raw_data_file[128] = "";
//     char output_file[128] = "";

//     if (argc < 9) {
//         my_printf("Example: shaper_calibrate AXIS=X NAME=shaper FREQ_START=1 FREQ_END=100 HZ_PER_SEC=1 \
//                 CHIPS=ADXL345 MAX_SMOOTHING=0.2 RAW_DATA=raw_data.txt OUTPUT=resonance\n");
//         return -1;
//     } else {
//         my_printf("shaper_calibrate: %s\n", argv[0]);
//         for (int i = 1; i < argc; i++) {
//             char* arg = argv[i];
//             if (strncmp(arg, "AXIS=", 5) == 0) {
//                 axis = arg + 5;
//                 my_printf("AXIS: %s\n", axis);
//             } else if (strncmp(arg, "NAME=", 5) == 0) {
//                 // name = arg + 5;
//                 sprintf(name, "%s", arg + 5);
//                 my_printf("NAME: %s\n", name);
//             } else if (strncmp(arg, "FREQ_START=", 11) == 0) {
//                 min_freq = atoi(arg + 11);
//                 my_printf("FREQ_START: %d\n", min_freq);
//             } else if (strncmp(arg, "FREQ_END=", 9) == 0) {
//                 max_freq = atoi(arg + 9);
//                 my_printf("FREQ_END: %d\n", max_freq);
//             } else if (strncmp(arg, "HZ_PER_SEC=", 11) == 0) {
//                 hz_per_sec = atoi(arg + 11);
//                 my_printf("HZ_PER_SEC: %d\n", hz_per_sec);
//             } else if (strncmp(arg, "CHIPS=", 6) == 0) {
//                 adxl345_chip_name = arg + 6;
//                 my_printf("CHIPS: %s\n", adxl345_chip_name);
//             } else if (strncmp(arg, "MAX_SMOOTHING=", 14) == 0) {
//                 max_smoothing = atof(arg + 14);
//                 my_printf("MAX_SMOOTHING: %f\n", max_smoothing);
//             } else if (strncmp(arg, "RAW_DATA=", 9) == 0) {
//                 // raw_data_file = arg + 9;
//                 sprintf(raw_data_file, "%s", arg + 9);
//                 my_printf("RAW_DATA: %s\n", raw_data_file);
//             } else if (strncmp(arg, "OUTPUT=", 7) == 0) {
//                 // output_file = arg + 7;
//                 sprintf(output_file, "%s", arg + 7);
//                 my_printf("OUTPUT: %s\n", output_file);
//             } else {
//                 my_printf("Unknown parameter: %s\n", arg);
//                 return -1;
//             }
//         }

//         // Validate integer and floating point conversion
//         if (min_freq <= 0) {
//             my_printf("Error: Invalid FREQ_START value. It must be a positive integer.\n");
//             return -1;
//         }
//         if (max_freq <= 0) {
//             my_printf("Error: Invalid FREQ_END value. It must be a positive integer.\n");
//             return -1;
//         }
//         if (hz_per_sec <= 0) {
//             my_printf("Error: Invalid HZ_PER_SEC value. It must be a positive integer.\n");
//             return -1;
//         }
//         if (max_smoothing <= 0.0f) {
//             my_printf("Error: Invalid MAX_SMOOTHING value. It must be a positive floating point number.\n");
//             return -1;
//         }
//     }

//     char* raw_file_name = raw_data_file;// "/root/Downloads/raw_data_x_20231228_120454.csv";
//     double** raw_data = NULL;
//     int raw_data_rows = 0;
//     const int raw_data_cols = 5;

//     FILE* file = fopen(raw_file_name, "r");
//     int total_lines = 0;
//     int max_rows = 50000;
//     int max_data_freq = 500;
//     if (file) {
//         char line[1024];
//         // Only take a portion of data will cause a problem??
//         // int start_line = 17500 - 20000; // Start reading data from the nth line
//         // int end_line = 17500 + 20000;   // Read until the mth line
//         int current_line = 0;
//         double step = 1;
//         double next_step = 0;


//         // First count the number of lines
//         while (fgets(line, sizeof(line), file)) {
//             total_lines++;
//         }

//         // Set the interval for data retrieval to ensure that the total number of lines does not exceed max_rows
//         if (total_lines > max_rows){
//             step = 1.0 * total_lines / max_rows;
//         }
//         next_step = step;

//         #if defined(__x86_64__) || defined(_M_X64)
//             raw_data = allocate_2d_array_double(total_lines, raw_data_cols);
//             if (!raw_data) {
//                 my_printf("Error: Failed to allocate memory for raw_data.\n");
//                 fclose(file);
//                 return -1;
//             }
//             my_printf("Running on x64 architecture\n");
//             step = 1;
//         #elif defined(__mips__) || defined(__mips)
//             raw_data = allocate_2d_array_double(max_rows, raw_data_cols);
//             // Code for MIPS 32-bit architecture
//             my_printf("Running on MIPS architecture\n");
//         #elif defined(__arm__) /* && (defined(__ARM_ARCH_7A__) || defined(__ARM_ARCH_7__) )*/
//             raw_data = allocate_2d_array_double(total_lines, raw_data_cols);
//             // Code for ARMv7 architecture (e.g., Raspberry Pi 2/3 running on 32-bit OS)
//             my_printf("Running on ARMv7 architecture (e.g., Raspberry Pi)\n");
//             step = 1;
//         #else
//             // Code for unknown architecture
//             my_printf("unknown architecture\n");
//         #endif

//         my_printf("total_lines: %d\n", total_lines);
//         my_printf("step: %f\n", step);

//         // Reset the file stream state and move the file pointer back to the beginning
//         fseek(file, 0, SEEK_SET);
//         while (fgets(line, sizeof(line), file)) {
//             if (current_line == 0 && strstr(line, "#") != NULL) {
//                 // If the current line contains "#", consider it as a header line and skip it
//                 current_line++;
//                 continue;
//             }
//             if (current_line++ < next_step){
//                 continue;
//             }
//             next_step += step;
//             char* token;
//             double value;
//             int i = 0;
//             int get_time_flg = 0;
//             int break_flg = 0;
//             double cur_data_time;
//             static double last_data_time = 0;
//             token = strtok(line, ",");
//             while (token != NULL) {
//                 value = atof(token);
//                 if (0 == get_time_flg){
//                     get_time_flg = 1;
//                     cur_data_time = value;
//                     // 时间满足条件才继续取数，否则跳过
//                     if (cur_data_time - last_data_time < 1.0 / max_data_freq){
//                         break_flg = 1;
//                         break;
//                     }
//                     last_data_time = cur_data_time;
//                 }
//                 token = strtok(NULL, ",");
//                 raw_data[raw_data_rows][i++] = value;
//             }
//             if (!break_flg){
//                 raw_data_rows++;
//             }
//         }
//         fclose(file);
//     } else {
//         fprintf(stderr, "can't open file %s\n", raw_file_name);
//     }

//     size_t memory_size = estimate_memory_usage(raw_data, raw_data_rows, raw_data_cols);
//     my_printf("raw_data vector size: %d\n", raw_data_rows);
//     my_printf("raw_data占用的估算内存大小: %f MB\n", (double)memory_size / 1024.0 / 1024.0);

//     struct CalibrationData calibration_data_total = {.size = 0};
//     int batch_size = max_data_freq; // 需要注意前提是数据量足够
//     int line_cnt = 0;
//     while(line_cnt + batch_size < raw_data_rows){
//         struct CalibrationData calibration_data;
//         calibration_data = process_accelerometer_data(raw_data + line_cnt, batch_size, raw_data_cols);
//         line_cnt += batch_size;
//         if (0 == calibration_data_total.size){
//             calibration_data_total = calibration_data; 
//         }else {
//             add_data(&calibration_data_total, &calibration_data);
//             free_calibration_data(&calibration_data);
//         }
//     }

//     normalize_to_frequencies(&calibration_data_total);
//     // save_calibration_data("/tmp/calib_data.csv", &calibration_data_total);
//     struct CalibrationResults calib_res;
//     calib_res = find_best_shaper(&calibration_data_total, max_smoothing);
//     save_calibration_res(output_file, name, &calibration_data_total, &calib_res);

//     #if defined(__x86_64__) || defined(_M_X64)
//         free_2d_array_double(raw_data, total_lines/* raw_data_rows */);
//     #elif defined(__mips__) || defined(__mips)
//         free_2d_array_double(raw_data, max_rows/* raw_data_rows */);
//     #elif defined(__arm__) /* && (defined(__ARM_ARCH_7A__) || defined(__ARM_ARCH_7__) )*/
//         free_2d_array_double(raw_data, total_lines/* raw_data_rows */);
//     #else
//     #endif
//     free_calibration_data(&calibration_data_total);
//     free_calibrationresults(&calib_res);
//     return 0;
// }

int shaper_calibrate_test(double max_smoothing, char* output_name, char *input_file, char* _output_file) {
    // Definitions for calibration parameters
    char name[32] = "default";
    char raw_data_file[128] = "";
    char output_file[128] = "";

    sprintf(name, "%s", output_name);
    my_printf("NAME: %s\n", name);
    sprintf(raw_data_file, "%s", input_file);
    my_printf("RAW_DATA: %s\n", raw_data_file);
    sprintf(output_file, "%s", _output_file);
    my_printf("OUTPUT: %s\n", output_file);

    char* raw_file_name = raw_data_file; 
    double** raw_data = NULL;
    int raw_data_rows = 0;
    const int raw_data_cols = 5;

    FILE* file = fopen(raw_file_name, "r");
    int total_lines = 0;
    int max_rows = 50000;
    if (file) {
        char line[1024];
        // Only take a portion of data will cause a problem??
        // int start_line = 17500 - 20000; // Start reading data from the nth line
        // int end_line = 17500 + 20000;   // Read until the mth line
        int current_line = 0;
        double step = 1;
        double next_step = 0;


        // First count the number of lines
        while (fgets(line, sizeof(line), file)) {
            total_lines++;
        }

        // Set the interval for data retrieval to ensure that the total number of lines does not exceed max_rows
        if (total_lines > max_rows){
            step = 1.0 * total_lines / max_rows;
        }
        next_step = step;

        #if defined(__x86_64__) || defined(_M_X64)
            raw_data = allocate_2d_array_double(total_lines, raw_data_cols);
            if (!raw_data) {
                my_printf("Error: Failed to allocate memory for raw_data.\n");
                fclose(file);
                return -1;
            }
            my_printf("Running on x64 architecture\n");
            step = 1;
        #elif defined(__mips__) || defined(__mips)
            raw_data = allocate_2d_array_double(max_rows, raw_data_cols);
            // Code for MIPS 32-bit architecture
            my_printf("Running on MIPS architecture\n");
        #elif defined(__arm__) /* && (defined(__ARM_ARCH_7A__) || defined(__ARM_ARCH_7__) )*/
            raw_data = allocate_2d_array_double(total_lines, raw_data_cols);
            // Code for ARMv7 architecture (e.g., Raspberry Pi 2/3 running on 32-bit OS)
            my_printf("Running on ARMv7 architecture (e.g., Raspberry Pi)\n");
            step = 1;
        #else
            // Code for unknown architecture
            my_printf("unknown architecture\n");
        #endif

        my_printf("total_lines: %d\n", total_lines);
        my_printf("step: %f\n", step);

        // Reset the file stream state and move the file pointer back to the beginning
        fseek(file, 0, SEEK_SET);
        while (fgets(line, sizeof(line), file)) {
            if (current_line == 0 && strstr(line, "#") != NULL) {
                // If the current line contains "#", consider it as a header line and skip it
                current_line++;
                continue;
            }
            if (current_line++ < next_step){
                continue;
            }
            next_step += step;
            char* token;
            double value;
            int i = 0;
            token = strtok(line, ",");
            while (token != NULL) {
                value = atof(token);
                token = strtok(NULL, ",");
                raw_data[raw_data_rows][i++] = value;
            }
            raw_data_rows++;
        }
        fclose(file);
    } else {
        fprintf(stderr, "can't open file %s\n", raw_file_name);
    }

    size_t memory_size = estimate_memory_usage(raw_data, raw_data_rows, raw_data_cols);
    my_printf("raw_data vector size: %d\n", raw_data_rows);
    my_printf("raw_data占用的估算内存大小: %f MB\n", (double)memory_size / 1024.0 / 1024.0);

    struct CalibrationData calibration_data = process_accelerometer_data(raw_data, raw_data_rows, raw_data_cols);
    normalize_to_frequencies(&calibration_data);
    struct CalibrationResults calib_res;
    calib_res = find_best_shaper(&calibration_data, max_smoothing);
    save_calibration_res(output_file, name, &calibration_data, &calib_res);
    #if defined(__x86_64__) || defined(_M_X64)
        free_2d_array_double(raw_data, total_lines/* raw_data_rows */);
    #elif defined(__mips__) || defined(__mips)
        free_2d_array_double(raw_data, max_rows/* raw_data_rows */);
    #elif defined(__arm__) /* && (defined(__ARM_ARCH_7A__) || defined(__ARM_ARCH_7__) )*/
        free_2d_array_double(raw_data, total_lines/* raw_data_rows */);
    #else
    #endif
    free_calibration_data(&calibration_data);
    free_calibrationresults(&calib_res);
    return 0;
}

void resonance_tester_print_test(char* str) {
    my_printf("%s\n", str);
}