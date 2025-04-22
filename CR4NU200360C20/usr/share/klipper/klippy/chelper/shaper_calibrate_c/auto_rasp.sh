make clean
make    LIBS='-lfftw3_rasp -lm' \
        TARGET='a.out' \
        CFLAGS='-Wall -I./ -Dmy_printf=printf -Dmy_perror=perror'