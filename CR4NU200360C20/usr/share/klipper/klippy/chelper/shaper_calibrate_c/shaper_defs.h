#ifndef __SHAPER_DEFS__
#define __SHAPER_DEFS__

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
// #include <vector>
// #include <string>

#define MAX_PULSE_LEN 5
#define SHAPER_VIBRATION_REDUCTION  20.
#define DEFAULT_DAMPING_RATIO  0.1
#define PRINT_MAX_FREQUENCIES  61
#define PRINT_MIN_FREQUENCIES  60
#define MAX_SHAPERS 6

#ifndef ARRAY_SIZE
#define ARRAY_SIZE(arr) (sizeof(arr) / sizeof((arr)[0]))
#endif

struct Shaper
{
    double A[MAX_PULSE_LEN];
    double T[MAX_PULSE_LEN];
    int size;
};
struct ShaperConfig
{
    // std::string name;
    char* name;
    struct Shaper (*init_func)(double shaper_freq, double damping_ratio);
    double min_freq;
};

// extern std::vector<ShaperConfig> INPUT_SHAPERS;
extern struct ShaperConfig INPUT_SHAPERS[];
// extern const int MAX_SHAPERS;

#endif