make clean
make CC=/home/zhan/Downloads/ingenic_linux-develop/tools/toolchains/mips-gcc720-glibc229/bin/mips-linux-gnu-gcc \
        DIST_LIB='c_helper.so' \
        CFLAGS='-Wall -g -O2 -fPIC -DCWCHELPER -I./ -Dmy_printf=errorf -Dmy_perror=errorf' \
        S_LDFLAGS='-Lshaper_calibrate_c -lfftw3_shared -lm' \
        LDFLAGS='-shared'
# scp ./c_helper.so root@172.23.210.109:/usr/share/klipper/klippy/chelper/c_helper.so