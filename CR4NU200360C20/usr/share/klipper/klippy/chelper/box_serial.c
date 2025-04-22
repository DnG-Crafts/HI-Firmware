#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <unistd.h>
#include <string.h>
#include "pyhelper.h"
#include "box_serial.h"
#include "compiler.h" // __visible

#define START_DATA 0x3C
#define END_DATA   0xff

static const unsigned char crc_table[] =
{
    0x00,0x31,0x62,0x53,0xc4,0xf5,0xa6,0x97,0xb9,0x88,0xdb,0xea,0x7d,0x4c,0x1f,0x2e,
    0x43,0x72,0x21,0x10,0x87,0xb6,0xe5,0xd4,0xfa,0xcb,0x98,0xa9,0x3e,0x0f,0x5c,0x6d,
    0x86,0xb7,0xe4,0xd5,0x42,0x73,0x20,0x11,0x3f,0x0e,0x5d,0x6c,0xfb,0xca,0x99,0xa8,
    0xc5,0xf4,0xa7,0x96,0x01,0x30,0x63,0x52,0x7c,0x4d,0x1e,0x2f,0xb8,0x89,0xda,0xeb,
    0x3d,0x0c,0x5f,0x6e,0xf9,0xc8,0x9b,0xaa,0x84,0xb5,0xe6,0xd7,0x40,0x71,0x22,0x13,
    0x7e,0x4f,0x1c,0x2d,0xba,0x8b,0xd8,0xe9,0xc7,0xf6,0xa5,0x94,0x03,0x32,0x61,0x50,
    0xbb,0x8a,0xd9,0xe8,0x7f,0x4e,0x1d,0x2c,0x02,0x33,0x60,0x51,0xc6,0xf7,0xa4,0x95,
    0xf8,0xc9,0x9a,0xab,0x3c,0x0d,0x5e,0x6f,0x41,0x70,0x23,0x12,0x85,0xb4,0xe7,0xd6,
    0x7a,0x4b,0x18,0x29,0xbe,0x8f,0xdc,0xed,0xc3,0xf2,0xa1,0x90,0x07,0x36,0x65,0x54,
    0x39,0x08,0x5b,0x6a,0xfd,0xcc,0x9f,0xae,0x80,0xb1,0xe2,0xd3,0x44,0x75,0x26,0x17,
    0xfc,0xcd,0x9e,0xaf,0x38,0x09,0x5a,0x6b,0x45,0x74,0x27,0x16,0x81,0xb0,0xe3,0xd2,
    0xbf,0x8e,0xdd,0xec,0x7b,0x4a,0x19,0x28,0x06,0x37,0x64,0x55,0xc2,0xf3,0xa0,0x91,
    0x47,0x76,0x25,0x14,0x83,0xb2,0xe1,0xd0,0xfe,0xcf,0x9c,0xad,0x3a,0x0b,0x58,0x69,
    0x04,0x35,0x66,0x57,0xc0,0xf1,0xa2,0x93,0xbd,0x8c,0xdf,0xee,0x79,0x48,0x1b,0x2a,
    0xc1,0xf0,0xa3,0x92,0x05,0x34,0x67,0x56,0x78,0x49,0x1a,0x2b,0xbc,0x8d,0xde,0xef,
    0x82,0xb3,0xe0,0xd1,0x46,0x77,0x24,0x15,0x3b,0x0a,0x59,0x68,0xff,0xce,0x9d,0xac
};

static uint8_t crc8(uint8_t *data, int len) {
    uint8_t crc = 0x00;
    while (len--)
    {
        crc = crc_table[crc ^ *data++];
    }
    return crc;
}

void __visible
box_send(int fd, uint8_t *msg, int len)
{
    /* start + len(1 byte) + data(len bytes) + check(1 byte) + stop */
    int length = 1 + 1 + len + 1 + 1;
    uint8_t *data = malloc(sizeof(uint8_t) * length);
    if (data == NULL)   {
        errorf("can not malloc");
        return;
    }
    memset(data, 0x00, sizeof(uint8_t) * length);
    *data = START_DATA;
    *(data + 1) = len;
    memcpy(data + 2, msg, len);

    uint8_t crc_data = crc8(data + 1, len + 1);
    *(data + len + 2) = crc_data;
    *(data + len + 3) = END_DATA;

    for (int i = 0; i < length; i++) {
        errorf("0x%x ", data[i]);
    }

    int ret = write(fd, data, length);
    if (ret < 0) {
        report_errno("write error", ret);
    }
    free(data);
}

#define STATUS_OK                   0x00
#define STATUS_DATA_ERROR           0x01
#define STATUS_MATERIAL_STORTAGE    0x02
#define STATUS_FUNC_ERR             0xfe
#define STATUS_NO_ACK               0xff

static uint8_t check_data(uint8_t *data, int data_len)
{
    int len = 0;
    uint8_t *cur = NULL;
    if (data_len == 0) {
	    return STATUS_NO_ACK;
    }
    for (int i = 0; i < data_len - 1; i++) {
        // check start data
        if (data[i] != START_DATA) {
		errorf("data[%d]:0x%x is not START_DATA.", i, data[i]);
            continue;
        }
        // check data len
        if (i + data[i + 1] + 1 > data_len) {
            break;
        }
	len = data[i + 1];
	if (i + len + 2 > data_len) {
		errorf("len = %d, i = %d", len, i);
            continue;
        }
	if (data[i + len + 3] != END_DATA) {
		errorf("data[%d]:0x%x is not END_DATA, len = %d", i + len + 2, data[i+len+2], len);
            continue;
        }
        cur = data + i;
	errorf("crc8 = 0x%x", crc8(cur + 1, len + 1));
        if (crc8(cur + 1, len + 1) == *(cur + len + 2)) {
		errorf("ret =  0x%x", *(cur + len + 1));
            return *(cur + len + 1);
        }
    }
    return STATUS_DATA_ERROR;
}

/*
 * return:  0x00 -> OK
 *          0x01 -> data error
 *          0x02 -> material shortage
 *          0xfe -> func error
 *          0xff -> no ack
 */
uint8_t __visible
box_read(int fd, uint8_t *data, int len, int *ret_len)
{
    uint8_t status = STATUS_OK;
    fd_set set;
    struct timeval timeout;
    int data_len = 0;
    int accumulate_len = 0;

    FD_ZERO(&set);
    FD_SET(fd, &set);
    timeout.tv_sec = 0;
    timeout.tv_usec = 100;

    memset(data, 0, len);
    while (1) {
    	int ret = select(fd + 1, &set, NULL, NULL, &timeout);
        if (ret == 0) {
            // errorf("no data");
	    break;
	} else if (ret < 0) {
	    errorf("select error");
	    return STATUS_FUNC_ERR;
	} else {
	    data_len = read(fd, data + accumulate_len, len - accumulate_len);
            if (data_len > 0) {
                errorf("Read %d bytes: 0x%x ", data_len, data[accumulate_len]);
                for (int j = 1; j < data_len; j++) {
                    errorf("0x%x ", data[accumulate_len + j]);
                }
	        accumulate_len += data_len;
	    } else if (data_len == 0) {
	    	errorf("no space to save data");
		break;
	    }
	}
    }
    *ret_len = accumulate_len;
    if (accumulate_len > 0) {
        errorf("final: Read %d bytes: 0x%x ", accumulate_len, data[0]);
        for (int i = 1; i < accumulate_len; i++) {
            errorf("0x%x ", data[i]);
        }
    }
    status = check_data(data, accumulate_len);

    return status;
}

uint8_t __visible
box_receive(int fd, uint8_t *data, int len, int *ret_len)
{
    uint8_t status = STATUS_OK;
    int data_len = 0, accumulate_len = 0;
    memset(data, 0, len);
    data_len = read(fd, data, len);
    *ret_len = 0;
    if (data_len > 0) {
        do {
	    if (accumulate_len + data_len > len) {
	        errorf("too mach datas");
		return STATUS_DATA_ERROR;
	    }
            errorf("Read %d bytes: 0x%x ", data_len, data[accumulate_len]);
            for (int j = 1; j < data_len; j++) {
                errorf("0x%x ", data[accumulate_len + j]);
            }
	    accumulate_len += data_len;
	    data_len = read(fd, data + accumulate_len, len - accumulate_len);
	} while (data_len > 0);
        *ret_len = accumulate_len;
        errorf("final: Read %d bytes: 0x%x ", accumulate_len, data[0]);
        for (int i = 1; i < accumulate_len; i++) {
            errorf("0x%x ", data[i]);
        }
    } else {
        // errorf("No data available\n");
        return STATUS_NO_ACK;
    }
    status = check_data(data, accumulate_len);
    return status;
}

#define ITEMS_NUM 4
static uint8_t *item[ITEMS_NUM] = {
    "vendor:",
    "type:",
    "name:",
    "color:",
};

#define SEPARATOR ';'

void __visible
box_data_process(uint8_t *src_data, int *len, struct material_info *info)
{
    int n = 0;
    char data[ITEMS_NUM][256] = {};
    uint8_t data_len[ITEMS_NUM] = {};
    uint8_t *cur = NULL;
    if (*len == 0) {
        return;
    }
    memset(data, 0, sizeof(data));
    memset(data_len, 0, sizeof(data_len));
    memset(info, 0, sizeof(info));
    for (int i = 0, j = 0; i < *len; i++) {
        if (strncmp(item[j], src_data + i, strlen(item[j])) == 0) {
            errorf("i = %d, j = %d", i, j);
            n = 0;
	    cur = src_data + i + strlen(item[j]);
	    do {
		n++;
	        if (*(cur + n) == SEPARATOR) {
		    memcpy(data[j], cur, n);
		    data_len[j] = n;
		    j++;
		    break;
		}
		errorf("n = %d", n);
	    } while (i + n < *len);
	    if (j == ITEMS_NUM) {
                break;
	    }
        }
    }
    memcpy(info->vendor, data[0], data_len[0]);
    memcpy(info->type, data[1], data_len[1]);
    memcpy(info->name, data[2], data_len[2]);
    memcpy(info->color, data[3], data_len[3]);
    errorf("info->vendor = %s", info->vendor);
    errorf("info->type = %s", info->type);
    errorf("info->name = %s", info->name);
    errorf("info->color = %s", info->color);
}
