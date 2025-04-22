make clean
make    DIST_LIB='c_helper.so' \
        CFLAGS='-Wall -g -O2 -fPIC -DCWCHELPER -I./ -Dmy_printf=errorf -Dmy_perror=errorf' \
        S_LDFLAGS='-Lshaper_calibrate_c -lfftw3_rasp_shared -lm' \
        LDFLAGS='-shared'