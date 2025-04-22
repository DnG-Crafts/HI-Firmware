#include <stdint.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef CWCHELPER
#include "pyhelper.h"
#endif

// 动态分配一维数组
double* allocate_1d_array_double(int size) {
    return (double*)malloc(size * sizeof(double));
}

// 动态分配二维数组
double** allocate_2d_array_double(int rows, int cols) {
    double** array = (double**)malloc(rows * sizeof(double*));
    for (int i = 0; i < rows; i++) {
        array[i] = (double*)malloc(cols * sizeof(double));
    }
    return array;
}

// 释放二维数组内存
void free_2d_array_double(double** array, int rows) {
    if (array) {
        for (int i = 0; i < rows; i++) {
            if(array[i]){
                free(array[i]);
                array[i] = NULL;
            }
        }
        free(array);
        array = NULL;
    }
}

