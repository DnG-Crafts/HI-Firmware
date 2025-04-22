CC = gcc
CFLAGS := -Wall -g -O2 -flto -fwhole-program -fno-use-linker-plugin -Dmy_printf=errorf -Dmy_perror=errorf
# 为了编译shaper_calibrate_c而增加的库
S_LDFLAGS := -Lshaper_calibrate_c -lfftw3_arm_shared -lm
# SRC_DIRS := shaper_calibrate_c 
# SOURCES := $(wildcard $(SRC_DIRS:%=%/*.c))
# OBJECTS := $(SOURCES:.c=.o)

OBJECTS = pyhelper.o serialqueue.o stepcompress.o itersolve.o trapq.o \
		  pollreactor.o msgblock.o trdispatch.o \
		  kin_cartesian.o kin_corexy.o kin_corexz.o kin_delta.o \
		  kin_deltesian.o kin_polar.o kin_rotary_delta.o kin_winch.o \
		  kin_extruder.o kin_shaper.o \
		  msgblock_485.o serial_485_queue.o\
		  shaper_calibrate_c/resonance_tester.o filament_change.o\
		  shaper_calibrate_c/shaper_calibrate.o \
		  shaper_calibrate_c/shaper_defs.o \
		  shaper_calibrate_c/mem.o

DIST_LIB = c_helper.so

all: $(DIST_LIB)

clean:
	@echo "Cleaning up directory."
	rm -f *.a *.o  $(DIST_LIB) *~
	find . -type f \( -name '*.o' -o -name '*.csv' -o -name '*.out' \) -exec rm -f {} +



$(DIST_LIB):$(OBJECTS)
	$(CC) $(LDFLAGS) -shared -fPIC -o $@ $(OBJECTS) $(S_LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -g -c -o $@ $<

