#ifndef __MEM_H__
#define __MEM_H__

double* allocate_1d_array_double(int size);
double** allocate_2d_array_double(int rows, int cols);
void free_2d_array_double(double** array, int rows);


#endif