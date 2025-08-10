#!/bin/sh


. /usr/share/libubox/jshn.sh

TMP_VERSION_FILE=/tmp/.cam_version.ota
CAM_VERSION_FILE=/tmp/.cam_version
VERSION_FILE=/mnt/UDISK/creality/userdata/config/cam_version.json
FW_ROOT_DIR=/usr/share/uvc/fw
CAM_OTA_FILE_NAME=
latest_version=
AUTO_CAM_LOG_DIR=/mnt/UDISK/creality/userdata/log/cam_fw
AUTO_HID_LOG_FILE=$AUTO_CAM_LOG_DIR/auto_hid.log
CAM_OTA_INFO_FILE=$AUTO_CAM_LOG_DIR/cam_ota_info.json


log_echo() {
    echo "[ $(date '+%Y-%m-%d %H:%M:%S') ] $*" >> $AUTO_HID_LOG_FILE
}

# 提取文件名中的日期和版本号
extract_version_info() {
    filename="$1"
    DATE=$(echo "$filename" | sed -n 's/.*-\([0-9]\{6\}\)V[0-9]\{3\}.*/\1/p')
    VERSION=$(echo "$filename" | sed -n 's/.*-[0-9]\{6\}V\([0-9]\{3\}\).*/\1/p')
    # [ -n "$DATE" ] && [ -n "$VERSION" ] && echo "${DATE}V${VERSION}"
    [ -n "$DATE" ] && echo "${DATE}"
    log_echo $DATE $VERSION
}

# 版本号比较，格式：250306V016
compare_versions() {
    if [ -z "$1" ]; then
        return 0
    fi

    # 使用数字比较
    if [ "$1" -gt "$2" ]; then
        return 1  # $1 比 $2 大
    else
        return 0  # $1 比 $2 小
    fi
}

fw_version_check()
{
    log_echo "$1 $2"
    
    model_name=$1
    count=0
    for file in "${FW_ROOT_DIR}"/*; do
        filename=$(basename "$file")
        log_echo "$filename"

        # 只处理包含型号的文件
        echo "$filename" | grep -q "$model_name" || continue
        count=$((count + 1))

        # 提取日期和版本号
        version=$(extract_version_info "$filename")
        CAM_OTA_FILE_NAME=$filename

        # 比较版本号，选出最新的文件
        if [ -z "$latest_version" ] || [ "$version" \> "$latest_version" ]; then
            latest_version="$version"
            CAM_OTA_FILE_NAME="$filename"
        fi
    done

    log_echo "catch $count fw files, version: $latest_version, cam_ota_file_name: $CAM_OTA_FILE_NAME"

    #如果是升级中途断电导致的HID升级，不校验版本是否最新，直接用最新版本升级
    if [ $count -gt 0 ]; then
        ret=1
    else
        ret=0
    fi

    return $ret
}

check_json_file() {
    local file=$1

    # 如果文件不存在或为空，则直接返回失败
    [ -f "$file" ] || return 0
    json_str=$(cat "$file")
    [ -n "$json_str" ] || return 0

    # 尝试加载 JSON 数据
    json_cleanup
    json_load "$json_str" || return 0
    json_select main_cam || return 0

    return 1
}

get_cam_ota_count()
{
    if [ -f "$CAM_OTA_INFO_FILE" ]; then
        json_load "$(cat "$CAM_OTA_INFO_FILE")"
        json_get_var ota_count ota_count          
        json_get_var succed_count succed_count          
        echo "${ota_count:-0} ${succed_count:-0}"
    else
        echo "0 0"
    fi
}

set_cam_ota_count()
{
    json_init
    json_add_int "ota_count" "$1"
    if [ "$2" -gt 0  ]; then
        json_add_int "succed_count" "$2"
    fi
    json_close_object
    json_dump > "$CAM_OTA_INFO_FILE"
    json_cleanup
}

fw_info()
{
    log_echo "$1"

    # tmp/.cam_version存在，说明是uvc升级，直接跳过
    if ! check_json_file "$TMP_VERSION_FILE"; then
        log_echo "main_cam is found in $TMP_VERSION_FILE, UVC upgrade"
        exit 0
    elif ! check_json_file "$CAM_VERSION_FILE"; then
        log_echo "main_cam is found in $CAM_VERSION_FILE, UVC upgrade"
        exit 0
    else
        log_echo "main_cam is not found in $TMP_VERSION_FILE or $CAM_VERSION_FILE"
        log_echo "power loss hid upgrade"
    fi

    if [ -f $VERSION_FILE ]; then
        json_str=$(cat $VERSION_FILE)

        json_load "$json_str" || { echo "JSON 解析失败"; exit 1; }
        json_select main_cam
        json_get_var manufactory manufactory
        json_get_var cur_version cur_version
        json_get_var power_en_pin power_en_pin

        log_echo "manufactory: $manufactory"
        log_echo "cur_version: $cur_version"
        log_echo "power_en_pin: $power_en_pin"
    else
        log_echo "VERSION FILE IS NOT FOUND, exit power off hid ota"
        return 0
    fi

    fw_version_check $manufactory $cur_version
    cam_upgrade_flag=$?
    log_echo "cam_upgrade_flag = $cam_upgrade_flag"
    return $cam_upgrade_flag
}

start_hid_ota()
{
    #创建计数文件夹
    if [ ! -d "$AUTO_CAM_LOG_DIR" ]; then
        log_echo "dir $AUTO_CAM_LOG_DIR is not exist, creating..."
        mkdir -p "$AUTO_CAM_LOG_DIR"
        log_echo "$AUTO_CAM_LOG_DIR created OK"
    fi

    #清空日志文件
    # : > $AUTO_HID_LOG_FILE

    fw_info /dev/hid/by-id/$1
    ret=$?
    log_echo "ret = $ret"

    if [ $ret -eq 1 ]; then
        if [ -f ${FW_ROOT_DIR}/${CAM_OTA_FILE_NAME} ]; then 
            result=$(get_cam_ota_count)   # 获取函数返回的字符串
            set -- $result  # 按空格拆分参数
            ota_count=$1
            succed_count=$2
            # read ota_count succed_count <<< "$result"  # 按空格分割字符串赋值到变量
            ota_count=$((ota_count + 1))
            log_echo "This is the $ota_count times cam OTA"

            log_echo "cam upgrade found, start power off hid ota"
            cam_util -i /dev/video0 -u -f "${FW_ROOT_DIR}/${CAM_OTA_FILE_NAME}" | while read line; do
                log_echo "ota_log: $line"
            done

            succed_count=$((succed_count + 1))
            set_cam_ota_count $ota_count $succed_count  # 重置OTA计数
            log_echo "The $ota_count-$succed_count times CAM OTA succesfull"
        else 
            log_echo "CAM_OTA_FILE_NAME is not found, exit power off hid ota"
            return 0
        fi
        
    else
        log_echo "this is not hid power off ota, skipping"
    fi
}

stop_hid_ota()
{
    log_echo "hid remove: $1"
    [ -f "$TMP_VERSION_FILE" ] && rm $TMP_VERSION_FILE && sync
}

#echo_console "MDEV=$MDEV ; ACTION=$ACTION ; DEVPATH=$DEVPATH ;\n"

#sync && echo 3 > /proc/sys/vm/drop_caches

case "${ACTION}" in
add)
        start_hid_ota ${MDEV}
        ;;
remove)
        stop_hid_ota ${MDEV}
        ;;
# cmd: ACTION=reload /usr/bin/auto_hid.sh
reload)
        reload_hid_ota
        ;;
# cmd: ACTION=stop /usr/bin/auto_hid.sh
stop)
        stop_all_hid_ota
        ;;
esac

exit 0