#include "shaper_defs.h"
#include <stdlib.h>
// #define _USE_MATH_DEFINES
#ifndef __USE_MISC
#define __USE_MISC
#endif
#include <math.h>
#ifdef CWCHELPER
#include "pyhelper.h"
#endif

struct Shaper get_zv_shaper(double shaper_freq, double damping_ratio) {
    struct Shaper shaper;
    double df = sqrt(1.0 - damping_ratio * damping_ratio);
    double K = exp(-damping_ratio * M_PI / df);
    double t_d = 1.0 / (shaper_freq * df);
    shaper.A[0] = 1.0; 
    shaper.A[1] = K;
    shaper.T[0] = 0.0;
    shaper.T[1] = 0.5 * t_d;
    shaper.size = 2;
    return shaper;
}

struct Shaper get_zvd_shaper(double shaper_freq, double damping_ratio) {
    struct Shaper shaper;
    double df = sqrt(1.0 - damping_ratio * damping_ratio);
    double K = exp(-damping_ratio * M_PI / df);
    double t_d = 1.0 / (shaper_freq * df);
    shaper.A[0] = 1.0;
    shaper.A[1] = K;
    shaper.A[2] = K * K;
    shaper.T[0] = 0.0;
    shaper.T[1] = 0.5 * t_d;
    shaper.T[2] = t_d;
    shaper.size = 3;
    return shaper;
}

struct Shaper get_mzv_shaper(double shaper_freq, double damping_ratio) {
    struct Shaper shaper; 
    double df = sqrt(1.0 - pow(damping_ratio, 2));
    double K = exp(-0.75 * damping_ratio * M_PI / df);
    double t_d = 1.0 / (shaper_freq * df);

    double a1 = 1.0 - 1.0 / sqrt(2.0);
    double a2 = (sqrt(2.0) - 1.0) * K;
    double a3 = a1 * K * K;

    shaper.A[0] = a1;
    shaper.A[1] = a2;
    shaper.A[2] = a3;
    shaper.T[0] = 0.0;
    shaper.T[1] = 0.375 * t_d;
    shaper.T[2] = 0.75 * t_d;
    shaper.size = 3;
    return shaper;
}

struct Shaper get_ei_shaper(double shaper_freq, double damping_ratio) {
    struct Shaper shaper;
    double v_tol = 1. / SHAPER_VIBRATION_REDUCTION; // vibration tolerance
    double df = sqrt(1. - pow(damping_ratio, 2));
    double K = exp(-damping_ratio * M_PI / df);
    double t_d = 1. / (shaper_freq * df);

    double a1 = .25 * (1. + v_tol);
    double a2 = .5 * (1. - v_tol) * K;
    double a3 = a1 * K * K;

    shaper.A[0] = a1;
    shaper.A[1] = a2;
    shaper.A[2] = a3;
    shaper.T[0] = 0.;
    shaper.T[1] = .5 * t_d;
    shaper.T[2] = t_d;
    shaper.size = 3;
    return shaper;
}

struct Shaper get_2hump_ei_shaper(double shaper_freq, double damping_ratio) {
    struct Shaper shaper;
    double v_tol = 1. / SHAPER_VIBRATION_REDUCTION; // vibration tolerance
    double df = sqrt(1. - damping_ratio*damping_ratio);
    double K = exp(-damping_ratio * M_PI / df);
    double t_d = 1. / (shaper_freq * df);

    double V2 = v_tol*v_tol;
    double X = pow(V2 * (sqrt(1. - V2) + 1.), 1./3.);
    double a1 = (3.*X*X + 2.*X + 3.*V2) / (16.*X);
    double a2 = (.5 - a1) * K;
    double a3 = a2 * K;
    double a4 = a1 * K * K * K;

    shaper.A[0] = a1;
    shaper.A[1] = a2;
    shaper.A[2] = a3;
    shaper.A[3] = a4;
    shaper.T[0] = 0.;
    shaper.T[1] = .5*t_d;
    shaper.T[2] = t_d;
    shaper.T[3] = 1.5*t_d;
    shaper.size = 4;
    return shaper;
}

struct Shaper get_3hump_ei_shaper(double shaper_freq, double damping_ratio) {
    struct Shaper shaper;
    double v_tol = 1.0 / SHAPER_VIBRATION_REDUCTION; // vibration tolerance
    double df = sqrt(1.0 - pow(damping_ratio, 2));
    double K = exp(-damping_ratio * M_PI / df);
    double t_d = 1.0 / (shaper_freq * df);

    double K2 = K * K;
    double a1 = 0.0625 * (1.0 + 3.0 * v_tol + 2.0 * sqrt(2.0 * (v_tol + 1.0) * v_tol));
    double a2 = 0.25 * (1.0 - v_tol) * K;
    double a3 = (0.5 * (1.0 + v_tol) - 2.0 * a1) * K2;
    double a4 = a2 * K2;
    double a5 = a1 * K2 * K2;

    shaper.A[0] = a1;
    shaper.A[1] = a2;
    shaper.A[2] = a3;
    shaper.A[3] = a4;
    shaper.A[4] = a5;
    shaper.T[0] = 0.0;
    shaper.T[1] = 0.5 * t_d;
    shaper.T[2] = t_d;
    shaper.T[3] = 1.5 * t_d;
    shaper.T[4] = 2.0 * t_d;
    shaper.size = 5;
    return shaper; 
}

struct ShaperConfig INPUT_SHAPERS[MAX_SHAPERS] = {
    { "zv",         get_zv_shaper,  21 },
    { "mzv",        get_mzv_shaper, 23 },
    { "zvd",        get_zvd_shaper, 29 },
    { "ei",         get_ei_shaper,  29 },
    { "2hump_ei",   get_2hump_ei_shaper, 39 },
    { "3hump_ei",   get_3hump_ei_shaper, 48 },
};

// const int MAX_SHAPERS = ARRAY_SIZE(INPUT_SHAPERS); 