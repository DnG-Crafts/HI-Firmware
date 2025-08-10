#!/bin/sh


. /usr/share/libubox/jshn.sh

CAM_FW_DIR=/usr/share/uvc/fw
AUTO_CAM_LOG_DIR=/mnt/UDISK/creality/userdata/log/cam_fw
AUTO_TEST_LOG_FILE=$AUTO_CAM_LOG_DIR/auto_ota_test.log
AUTO_HID_LOG_FILE=$AUTO_CAM_LOG_DIR/auto_hid.log
AUTO_UVC_LOG_FILE=$AUTO_CAM_LOG_DIR/auto_uvc.log
CAM_OTA_INFO_FILE=$AUTO_CAM_LOG_DIR/cam_ota_info.json
NEW_FILENAME=
ota_count=0
succed_count=0

log_echo() {
    echo "[ $(date '+%Y-%m-%d %H:%M:%S') ] $*" >> $AUTO_TEST_LOG_FILE
    echo "[ $(date '+%Y-%m-%d %H:%M:%S') ] $*"
}

get_cam_ota_count()
{
    if [ -f "$CAM_OTA_INFO_FILE" ]; then
        json_str=$(cat "$CAM_OTA_INFO_FILE")
        if [ -z "$json_str" ]; then
            echo "0 0"
        else
            json_load "$json_str"
            json_get_var ota_count_tmp ota_count       # 从 JSON 中提取 ota_count
            json_get_var succed_count_tmp succed_count # 从 JSON 中提取 succed_count
            ota_count_tmp=${ota_count_tmp:-$ota_count}              # 如果未定义，默认值为 0
            succed_count_tmp=${succed_count_tmp:-$succed_count}        # 如果未定义，默认值为 0
            echo "$ota_count_tmp $succed_count_tmp"
        fi
    else
        echo "0 0"
    fi
}

cp_ota_fw_new_version()
{
    SRC_FILE="$1"

    if [ ! -f $SRC_FILE ]; then
        log_echo "$SRC_FILE not found, auto test quit"
        exit 1
    fi

    # 提取文件的目录、名称、日期和后缀
    DIR=$(dirname "$SRC_FILE")
    BASENAME=$(basename "$SRC_FILE")

    # 使用 `sed` 提取 6 位日期
    DATE=$(echo "$BASENAME" | sed -n 's/.*-\([0-9]\{6\}\)V[0-9]\{3\}.*/\1/p')
    # VERSION=$(echo "$BASENAME" | sed -n 's/.*-[0-9]\{6\}V\([0-9]\{3\}\).*/\1/p')

    # 日期加 1
    NEW_DATE=$(expr $DATE + 1)
    # 生成新文件名
    NEW_FILENAME=$(echo "$BASENAME" | sed "s/$DATE/$NEW_DATE/")

    # 复制文件
    cp "$SRC_FILE" "$DIR/$NEW_FILENAME"
}

start_auto_uvc()
{
    total_count=$2

    # 清空计数文件
    [ -f $CAM_OTA_INFO_FILE ] && : > $CAM_OTA_INFO_FILE  
    # 清空升级日志
    [ -f $AUTO_HID_LOG_FILE ] && : > $AUTO_HID_LOG_FILE
    [ -f $AUTO_UVC_LOG_FILE ] && : > $AUTO_UVC_LOG_FILE 
    [ -f $AUTO_TEST_LOG_FILE ] && : > $AUTO_TEST_LOG_FILE 

    log_echo "Starting Auto UVC service..."   
    log_echo "total ota count: $total_count"   

    cp_ota_fw_new_version "$1"

    #重启cam
    echo 1 > /sys/class/gpio/gpio210/value
    sleep 2
    echo 0 > /sys/class/gpio/gpio210/value

    start_time=$(date +%s)
    
    result=$(get_cam_ota_count)   # 获取函数返回的字符串
    set -- $result  # 按空格拆分参数
    ota_count=$1
    prev_count=$2

    while true; do 
        result=$(get_cam_ota_count)   # 获取函数返回的字符串
        set -- $result  # 按空格拆分参数
        ota_count=$1
        count=$2
        # log_echo "result=$result"

        if [ "$count" -ne "$prev_count" ]; then
            log_echo "ota test total count $total_count , current count: $ota_count, succed_count: $count"
            end_time=$(date +%s)
            elapsed_time=$((end_time - start_time))
            log_echo "the $ota_count times cam ota, cost $elapsed_time seconds"
            start_time=$(date +%s)

            prev_count=$count  # 更新 prev_count
            if [ "$count" -ge $total_count ]; then
                break
            fi
        fi

        sleep 1  # 1秒延时，避免 CPU 过载
    done

    rm "$CAM_FW_DIR/$NEW_FILENAME"
}


# Example usage: 
# $1 OTA file filename 
# $2 total_count
start_auto_uvc "$1" "$2"
