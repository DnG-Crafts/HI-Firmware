make clean
make CC=/home/zhan/Downloads/ingenic_linux-develop/tools/toolchains/mips-gcc720-glibc229/bin/mips-linux-gnu-gcc \
        LIBS='-lfftw3 -lm' \
        CFLAGS='-Wall -I./ -Dmy_printf=printf -Dmy_perror=perror'
scp a.out root@172.23.210.109:/root/Downloads
