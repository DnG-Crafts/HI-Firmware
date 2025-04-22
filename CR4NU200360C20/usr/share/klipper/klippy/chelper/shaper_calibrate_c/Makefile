CC = /usr/bin/gcc 
LIBS = -lfftw3_x86_64 -lm
# 编译标志
CFLAGS = -Wall -g -I./ 
# 链接标志
LDFLAGS = -L./ $(LIBS)
# 目标文件
TARGET = a.out
# 输出路径
OUTPUT_PATH = ./
# Set the target with the platform-specific output path
TARGET := $(OUTPUT_PATH)$(TARGET)
# 源文件
SRCS = \
	resonance_tester.c \
	shaper_calibrate.c \
	shaper_defs.c \
	mem.c

# 生成目标文件
OBJS = $(SRCS:.c=.o)
# 默认规则
all: $(TARGET)
# 生成可执行文件
$(TARGET): $(OBJS)
	$(CC) -o $@ $^ $(LDFLAGS)
# 生成目标文件
%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<
# 清理生成的文件
clean:
	rm -f $(OBJS) $(TARGET)
