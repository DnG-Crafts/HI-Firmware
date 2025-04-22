make clean
make CFLAGS='-Wall -g -O2 -fPIC -DCWCHELPER -I./ -Dmy_printf=errorf -Dmy_perror=errorf'