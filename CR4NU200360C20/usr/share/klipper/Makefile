# Klipper build system
#
# Copyright (C) 2016-2020  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

# host file
host-tool-src = tool/host_crc16.c

# Output directory
OUT=out/

# Kconfig includes
export KCONFIG_CONFIG     := $(CURDIR)/.config
-include $(KCONFIG_CONFIG)

# Common command definitions
CC=$(CROSS_PREFIX)gcc
AS=$(CROSS_PREFIX)as
LD=$(CROSS_PREFIX)ld
OBJCOPY=$(CROSS_PREFIX)objcopy
OBJDUMP=$(CROSS_PREFIX)objdump
STRIP=$(CROSS_PREFIX)strip
CPP=cpp
PYTHON=python3

# Source files
src-y =
dirs-y = src

# Default compiler flags
cc-option=$(shell if test -z "`$(1) $(2) -S -o /dev/null -xc /dev/null 2>&1`" \
    ; then echo "$(2)"; else echo "$(3)"; fi ;)

CFLAGS := -I$(OUT) -Isrc -I$(OUT)board-generic/ -std=gnu11 -O2 -MD \
    -Wall -Wold-style-definition $(call cc-option,$(CC),-Wtype-limits,) \
    -ffunction-sections -fdata-sections -fno-delete-null-pointer-checks
CFLAGS += -flto -fwhole-program -fno-use-linker-plugin -ggdb3

OBJS_klipper.elf = $(patsubst %.c, $(OUT)src/%.o,$(src-y))
OBJS_klipper.elf += $(OUT)compile_time_request.o
CFLAGS_klipper.elf = $(CFLAGS) -Wl,--gc-sections -Wl,-Map,out/klipper.map

CPPFLAGS = -I$(OUT) -P -MD -MT $@

bootloader_src-y = 
bootloader_dirs-y = bootloader
BOOTLOADER_CFLAGS := -I$(OUT) -I$(OUT)board -std=gnu11 -O2 -MD \
					 -Wall -Wold-style-definition $(call cc-option,$(CC),-Wtype-limits,) \
					 -ffunction-sections -fdata-sections -fno-delete-null-pointer-checks
OBJS_bootloader.elf = $(patsubst %.c, $(OUT)bootloader/%.o,$(bootloader_src-y))
CFLAGS_bootloader.elf = $(BOOTLOADER_CFLAGS) -Wl,--gc-sections

# Default targets
target-y := $(OUT)klipper.elf
target-y += $(OUT)hostCrc16.elf
# target-y += $(OUT)src/prtouch_v2.o
target-$(CONFIG_BOARD_INFO_CONFIGURE) +=$(OUT)bootloader.elf

all:

# Run with "make V=1" to see the actual compile commands
ifdef V
Q=
else
Q=@
MAKEFLAGS += --no-print-directory
endif

##### Process board hardware and firmware version

ifeq ($(CONFIG_BOARD_INFO_CONFIGURE),y)

ifeq ($(CONFIG_MAIN_MCU_BOARD),y)
board_type := mcu
else ifeq ($(CONFIG_NOZZLE_MCU_BOARD),y)
board_type := noz
else ifeq ($(CONFIG_BED_MCU_BOARD),y)
board_type := bed
endif

ifneq ($(CONFIG_MCU_MENU),)
mcu_menu := $(patsubst "%",%,$(CONFIG_MCU_MENU))
else
mcu_menu :=
endif

ifneq ($(CONFIG_MCU_TYPE),)
mcu_type := $(patsubst "%",%,$(CONFIG_MCU_TYPE))
else
mcu_type :=
endif

board_hw_version := $(board_type)$(CONFIG_MCU_BOARD_ID)_$(CONFIG_MCU_BOARD_HW_VER)_$(mcu_menu)$(mcu_type)
board_fw_version := $(board_type)$(CONFIG_MCU_BOARD_ID)_$(CONFIG_MCU_BOARD_FW_VER)_$(CONFIG_MCU_BOARD_FW_RESERVED)

CFLAGS += -DBOARD_FW_VERSION=\"$(board_fw_version)\"
BOOTLOADER_CFLAGS += -DBOARD_HW_VERSION=\"$(board_hw_version)\"

export board_hw_version board_fw_version
endif

# Include board specific makefile
include src/Makefile
-include src/$(patsubst "%",%,$(CONFIG_BOARD_DIRECTORY))/Makefile
-include src/bootloader/Makefile

################ Main build rules

$(OUT)%.o: %.c $(OUT)autoconf.h
	@echo "  Compiling $@"
	$(Q)$(CC) $(CFLAGS) -c $< -o $@

$(OUT)%.ld: %.lds.S $(OUT)autoconf.h
	@echo "  Preprocessing $@"
	$(Q)$(CPP) -I$(OUT) -P -MD -MT $@ $< -o $@

$(OUT)klipper.elf: $(OBJS_klipper.elf) $(OUT)hostCrc16.elf
	@echo "  Linking $@"
	$(Q)$(CC) $(OBJS_klipper.elf) $(CFLAGS_klipper.elf) -o $@
	$(Q)scripts/check-gcc.sh $@ $(OUT)compile_time_request.o

$(OUT)bootloader/src/generic/%.ld: src/bootloader/src/generic/%.lds.S $(OUT)autoconf.h
	@echo "  Preprocessing $@"
	$(Q)$(CPP) -I$(OUT) -P -MD -MT $@ $< -o $@

$(OUT)bootloader/%.o: src/bootloader/%.c $(OUT)autoconf.h
	@echo "  Compiling $@"
	$(Q)$(CC) $(BOOTLOADER_CFLAGS) -c $< -o $@

$(OUT)bootloader.elf: $(OBJS_bootloader.elf)
	@echo " Linking $@"
	$(Q)$(CC) $(OBJS_bootloader.elf) $(CFLAGS_bootloader.elf) -o $@

$(OUT)hostCrc16.elf: $(host-tool-src)
	@echo "  Compiling and Linking $@"
	$(Q)gcc $< -o $@
	
################ Compile time requests

$(OUT)%.o.ctr: $(OUT)%.o
	$(Q)$(OBJCOPY) -j '.compile_time_request' -O binary $^ $@

$(OUT)compile_time_request.o: $(patsubst %.c, $(OUT)src/%.o.ctr,$(src-y)) ./scripts/buildcommands.py
	@echo "  Building $@"
	$(Q)cat $(patsubst %.c, $(OUT)src/%.o.ctr,$(src-y)) | tr -s '\0' '\n' > $(OUT)compile_time_request.txt
	$(Q)$(PYTHON) ./scripts/buildcommands.py -d $(OUT)klipper.dict -t "$(CC);$(AS);$(LD);$(OBJCOPY);$(OBJDUMP);$(STRIP)" $(OUT)compile_time_request.txt $(OUT)compile_time_request.c
	$(Q)$(CC) $(CFLAGS) -c $(OUT)compile_time_request.c -o $@

################ Auto generation of "board/" include file link

create-board-link:
	@echo "  Creating symbolic link $(OUT)board"
	$(Q)mkdir -p $(addprefix $(OUT), $(dirs-y))
	$(Q)rm -f $(OUT)*.d $(patsubst %,$(OUT)%/*.d,$(dirs-y))
	$(Q)mkdir -p $(addprefix $(OUT), $(bootloader_dirs-y))
	$(Q)rm -f $(patsubst %,$(OUT)%/*.d,$(bootloader_dirs-y))
	$(Q)rm -f $(OUT)board
	$(Q)ln -sf $(CURDIR)/src/$(CONFIG_BOARD_DIRECTORY) $(OUT)board
	$(Q)mkdir -p $(OUT)board-generic
	$(Q)rm -f $(OUT)board-generic/board
	$(Q)ln -sf $(CURDIR)/src/generic $(OUT)board-generic/board

# Hack to rebuild OUT directory and reload make dependencies on Kconfig change
$(OUT)board-link: $(KCONFIG_CONFIG)
	$(Q)mkdir -p $(OUT)
	$(Q)echo "# Makefile board-link rule" > $@
	$(Q)$(MAKE) create-board-link
include $(OUT)board-link

################ Kconfig rules

$(OUT)autoconf.h: $(KCONFIG_CONFIG)
	@echo "  Building $@"
	$(Q)mkdir -p $(OUT)
	$(Q) KCONFIG_AUTOHEADER=$@ $(PYTHON) lib/kconfiglib/genconfig.py src/Kconfig

$(KCONFIG_CONFIG) olddefconfig: src/Kconfig
	$(Q)$(PYTHON) lib/kconfiglib/olddefconfig.py src/Kconfig

menuconfig:
	$(Q)$(PYTHON) lib/kconfiglib/menuconfig.py src/Kconfig
	@echo "  Board HW Ver: $(board_hw_version)"
	@echo "  Board FW Ver: $(board_fw_version)"

%_defconfig: src/configs/%_defconfig
	@echo "  Load configuration: $@"
	$(Q)cp -v src/configs/$@ $(KCONFIG_CONFIG)

################ Generic rules

# Make definitions
.PHONY : all clean distclean olddefconfig menuconfig create-board-link FORCE
.DELETE_ON_ERROR:

all: $(target-y)

clean:
	$(Q)rm -rf $(OUT)

distclean: clean
	$(Q)rm -f .config .config.old

-include $(OUT)*.d $(patsubst %,$(OUT)%/*.d,$(dirs-y))
