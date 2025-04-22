make clean
make CC=/home/longer/opt/toolchain-sunxi-glibc-gcc-830/toolchain/bin/arm-openwrt-linux-gnueabi-gcc \
        STAGING_DIR=/home/longer/opt/sysroot \
        DIST_LIB='c_helper.so' \
        CFLAGS='-Wall -g -O2 -fPIC -DCWCHELPER -I./ -Dmy_printf=errorf -Dmy_perror=errorf' \
        S_LDFLAGS='-Lshaper_calibrate_c -lfftw3_arm_shared -lm' \
        LDFLAGS='-shared'
# scp ./c_helper.so root@172.23.210.109:/usr/share/klipper/klippy/chelper/c_helper.so