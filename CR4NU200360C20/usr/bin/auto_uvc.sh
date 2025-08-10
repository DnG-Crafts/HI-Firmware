#!/bin/sh

#set -x

. /usr/share/libubox/jshn.sh

PROG=/usr/bin/cam_app
PROG_SUB=/usr/bin/cam_sub_app
WEBRTC_LOCAL=/usr/bin/webrtc_local
TMP_VERSION_FILE=/tmp/.cam_version
VERSION_FILE=/mnt/UDISK/creality/userdata/config/cam_version.json
FW_ROOT_DIR=/usr/share/uvc/fw
CAM_OTA_FILE_NAME=
latest_version=
AUTO_CAM_LOG_DIR=/mnt/UDISK/creality/userdata/log/cam_fw
AUTO_UVC_LOG_FILE=$AUTO_CAM_LOG_DIR/auto_uvc.log
CAM_OTA_INFO_FILE=$AUTO_CAM_LOG_DIR/cam_ota_info.json

MAIN_CAM=0
MAIN_PIC_WIDTH=1920
MAIN_PIC_HEIGHT=1080
MAIN_PIC_FPS=15


GRAPHIC_CUT_CENTER_X=
GRAPHIC_CUT_CENTER_Y=
GRAPHIC_CUT_WIDTH=
GRAPHIC_CUT_HEIGHT=

MODEL=$(/usr/bin/get_sn_mac.sh model)

if [ "$MODEL" = "F009" ] || [ "$MODEL" = "F011" ] || [ "$MODEL" = "F018" ]; then
    MAIN_PIC_WIDTH=1280
    MAIN_PIC_HEIGHT=720
fi

SUB_CAM=1
SUB_PIC_WIDTH=1600
SUB_PIC_HEIGHT=1200
SUB_PIC_FPS=5

TIME_OUT_CNT=15

echo_console()
{
    printf "$*" > /dev/console
}

log_echo() {
    echo "[ $(date '+%Y-%m-%d %H:%M:%S') ] $*" >> $AUTO_UVC_LOG_FILE
}

# 提取文件名中的日期和版本号
extract_version_info() {
    filename="$1"
    DATE=$(echo "$filename" | sed -n 's/.*-\([0-9]\{6\}\)V[0-9]\{3\}.*/\1/p')
    VERSION=$(echo "$filename" | sed -n 's/.*-[0-9]\{6\}V\([0-9]\{3\}\).*/\1/p')
    [ -n "$DATE" ] && echo "${DATE}"
    log_echo $DATE
}

# 版本号比较，格式：250306V016
compare_versions() {
    if [ -z "$1" ]; then
        return 0
    fi

    log_echo "compare_versions $1 $2"
    echo_console "compare_versions $1 $2"

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

    log_echo "catch $count fw files, version: $latest_version"
    log_echo "cam_ota_file_name: $CAM_OTA_FILE_NAME"

    if [ $count -gt 0 ]; then
        log_echo $latest_version  $2
        compare_versions $latest_version  $2
        ret=$?
        log_echo "ret = $ret"
    else
        ret=0 
    fi

    return $ret
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
    case $1 in
        *main*)
            local is_main=1
        ;;
        *sub*)
            local is_main=0
        ;;
    esac
    
    [ -x /usr/bin/cam_util ] && {
        FwVersion=$(cam_util -i $1 -g | grep -w FwVersion | awk -F ' ' -e '{print $2}')
        if [ "x$FwVersion" != "x" ]; then
            case $FwVersion in
                STD*|C400100*)
                    manufactory=$(echo $FwVersion | cut -d '_' -f 1)
                    cur_version=$(echo $FwVersion | cut -d '_' -f 2)
                    ;;
                *)
                    manufactory=${FwVersion:15:9}
                    cur_version=${FwVersion:25:6}
                    ;;
            esac

            case $manufactory in
                "STsmart_-" | "STJC-000I")
                    if [ $(ls ${FW_ROOT_DIR}/STsmart/*.src | wc -l) -eq 1 ]; then
                        fw_path=$(ls ${FW_ROOT_DIR}/STsmart/*.src)
                        tmp=$(basename $fw_path)
                        tmp=${tmp%.src}
                        fw_version=${tmp##*_}
                    else
                        fw_version=0
                        fw_path=
                        echo_console "we should keep only one firmware file for STsmart!"
                    fi
                    ;;
                *)
                    ;;
            esac

            if [ -f $TMP_VERSION_FILE ]; then
                json_load_file $TMP_VERSION_FILE
            else
                json_init
            fi
            if [ "x$is_main" = "x1" ]; then
                json_add_object "main_cam"
                log_echo "main_cam"
            else
                json_add_object "sub_cam"
                log_echo "sub_cam"
            fi
            json_add_string "video_node" $1
            json_add_string "manufactory" $manufactory
            json_add_string "cur_version" $cur_version
            json_add_string "newest_fw_path" $fw_path
            if [ $fw_version -gt $cur_version ]; then
                json_add_boolean "can_update" 1
            else
                json_add_boolean "can_update" 0
            fi
            json_close_object
            json_dump > $TMP_VERSION_FILE
            json_cleanup

            [ "x$is_main" = "x1" ] || return

            json_init
            json_add_object "main_cam"
            json_add_string "manufactory" $manufactory
            json_add_string "cur_version" $cur_version
            json_add_string "power_en_pin" $power_en_pin
            json_close_object
            json_dump > $VERSION_FILE
            json_cleanup
        fi
    }
    
    fw_version_check $manufactory $cur_version
    cam_upgrade_flag=$?
    log_echo "cam_upgrade_flag = $cam_upgrade_flag"
    return $cam_upgrade_flag
}

fw_info_check()
{
    video_node=$1
    fw_info /dev/v4l/by-id/$1
    if [ $? -eq 1 ]; then
        result=$(get_cam_ota_count)   # 获取函数返回的字符串
        set -- $result  # 按空格拆分参数
        ota_count=$1
        succed_count=$2
        ota_count=$((ota_count + 1))
        log_echo "This is the $ota_count times cam OTA"

        cp $TMP_VERSION_FILE $TMP_VERSION_FILE.ota && sync
        cam_util -i /dev/video0 -u -f "${FW_ROOT_DIR}/${CAM_OTA_FILE_NAME}" | while read line; do
            log_echo "ota_log: $line"
        done
        rm $TMP_VERSION_FILE.ota && sync

        succed_count=$((succed_count + 1))
        set_cam_ota_count $ota_count $succed_count  # 重置OTA计数

        log_echo "The $ota_count-$succed_count times CAM OTA succesfull"

        return 1
    fi

    return 0
}

set_graphic_cut_info()
{
     if [ "$MODEL" = "F021" ]; then
        cam_util -i /dev/v4l/by-id/$1 set_cut_param $GRAPHIC_CUT_CENTER_X $GRAPHIC_CUT_CENTER_Y \
                $GRAPHIC_CUT_WIDTH $GRAPHIC_CUT_HEIGHT

        log_echo "model: $MODEL, set_cut_param $GRAPHIC_CUT_CENTER_X $GRAPHIC_CUT_CENTER_Y \
            $GRAPHIC_CUT_WIDTH $GRAPHIC_CUT_HEIGHT"
    fi
}

start_uvc()
{
    #创建计数文件夹
    if [ ! -d "$AUTO_CAM_LOG_DIR" ]; then
        log_echo "dir $AUTO_CAM_LOG_DIR is not exist, creating..."
        mkdir -p "$AUTO_CAM_LOG_DIR"
        log_echo "$AUTO_CAM_LOG_DIR created OK"
    fi

    #清空日志文件
    # : > $AUTO_UVC_LOG_FILE

    local count=0
    case $1 in
        main-video*)
            echo_console "start cam_app service for $1 : "
            logger -t uvc "start cam_app service for $1"

            fw_info_check $1
            if [ $? -eq 1 ]; then
                exit 0
            fi

            set_graphic_cut_info $1

            # wait for UDISK mounted
            while true
            do
                if grep -wq UDISK /proc/mounts ; then
                    logger -t uvc "UDISK mounted"
                    break
                else
                    sleep 0.4
                    let count+=1
                fi

                # time out 6s
                if [ $count -gt $TIME_OUT_CNT ]; then
                    break
                fi
            done

            start-stop-daemon -S -b -m -p /var/run/$1.pid \
                --exec $PROG -- -i /dev/v4l/by-id/$1 -t $MAIN_CAM \
                -w $MAIN_PIC_WIDTH -h $MAIN_PIC_HEIGHT -f $MAIN_PIC_FPS \
                -c
            [ $? = 0 ] && echo_console "OK\n" || echo_console "FAIL\n"

            sleep 1

            start-stop-daemon -S -b -m -p /var/run/$1_webrtc_local.pid \
                --exec $WEBRTC_LOCAL
        ;;
        sub-video*)
            echo_console "start cam_app service for $1 : "

            fw_info /dev/v4l/by-id/$1

            start-stop-daemon -S -b -m -p /var/run/$1.pid \
                --exec $PROG_SUB -- -i /dev/v4l/by-id/$1 -t $SUB_CAM \
                -w $SUB_PIC_WIDTH -h $SUB_PIC_HEIGHT -f $SUB_PIC_FPS \
                -c
            [ $? = 0 ] && echo_console "OK\n" || echo_console "FAIL\n"
        ;;
    esac
}

stop_uvc()
{
    local count=0
    case $1 in
        main-video*)
            echo_console "stop cam_app service for $1 : "

            start-stop-daemon -K -p /var/run/$1.pid

            if [ $? = 0 ]; then
                echo_console "OK\n"

                # wait for process exit
                while true
                do
                    if [ -d /proc/$(cat /var/run/$1.pid) ]; then
                        sleep 0.2
                        let count+=1
                    else
                        break
                    fi
                    # time out 3s, then send kill signal to process
                    if [ $count -gt $TIME_OUT_CNT ]; then
                        kill -9 $(cat /var/run/$1.pid)
                        sleep 0.5
                    fi
                done

            else
                echo_console "FAIL\n"
            fi

            start-stop-daemon -K -p /var/run/$1_webrtc_local.pid

            [ -f $TMP_VERSION_FILE ] && {
                jq -cMS 'del(.main_cam)' $TMP_VERSION_FILE > $TMP_VERSION_FILE.tmp && \
                mv $TMP_VERSION_FILE.tmp $TMP_VERSION_FILE && sync
                [ $(jq -e 'has("sub_cam")' $TMP_VERSION_FILE) = "true" ] || rm -rf $TMP_VERSION_FILE
            }
        ;;

        sub-video*)
            echo_console "stop cam_app service for $1 : "

            start-stop-daemon -K -p /var/run/$1.pid

            if [ $? = 0 ]; then
                echo_console "OK\n"

                # wait for process exit
                while true
                do
                    if [ -d /proc/$(cat /var/run/$1.pid) ]; then
                        sleep 0.2
                        let count+=1
                    else
                        break
                    fi
                    # time out 3s, then send kill signal to process
                    if [ $count -gt $TIME_OUT_CNT ]; then
                        kill -9 $(cat /var/run/$1.pid)
                        sleep 0.5
                    fi
                done

            else
                echo_console "FAIL\n"
            fi

            [ -f $TMP_VERSION_FILE ] && {
                jq -cMS 'del(.sub_cam)' $TMP_VERSION_FILE > $TMP_VERSION_FILE.tmp && \
                mv $TMP_VERSION_FILE.tmp $TMP_VERSION_FILE && sync
                [ $(jq -e 'has("main_cam")' $TMP_VERSION_FILE) = "true" ] || rm -rf $TMP_VERSION_FILE
            }
    esac
}

reload_uvc()
{
    [ -d /dev/v4l/by-id ] && {
        DEVS=$(ls /dev/v4l/by-id)
        if [ "x$DEVS" != "x" ]; then
            for dev in $DEVS
            do
                stop_uvc $dev
                start_uvc $dev
            done
        fi
    }
}

stop_all_uvc()
{
    [ -d /dev/v4l/by-id ] && {
        DEVS=$(ls /dev/v4l/by-id)
        if [ "x$DEVS" != "x" ]; then
            for dev in $DEVS
            do
                stop_uvc $dev
            done
        fi
    }
}

#echo_console "MDEV=$MDEV ; ACTION=$ACTION ; DEVPATH=$DEVPATH ;\n"

#sync && echo 3 > /proc/sys/vm/drop_caches

case "${ACTION}" in
add)
        start_uvc ${MDEV}
        ;;
remove)
        stop_uvc ${MDEV}
        ;;
# cmd: ACTION=reload /usr/bin/auto_uvc.sh
reload)
        reload_uvc
        ;;
# cmd: ACTION=stop /usr/bin/auto_uvc.sh
stop)
        stop_all_uvc
        ;;
esac

exit 0
