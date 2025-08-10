#!/bin/sh

AUTO_CAM_LOG_DIR=/mnt/UDISK/creality/userdata/log/cam_fw
CAM_RESTART_LOG_FILE=$AUTO_CAM_LOG_DIR/cam_restart.log

log_echo() {
    echo "[ $(date '+%Y-%m-%d %H:%M:%S') ] $*" >> $CAM_RESTART_LOG_FILE
}

help()
{
    echo "Usage: $0 <on|off|restart>"
}

if [ $# -eq 1 ]; then
    model=$(get_sn_mac.sh model)

    case $1 in
    "on")
    ;;

    "off")
    ;;

    "restart")
        if [ "$model" = "F009" ] || [ "$model" = "F011" ] || [ "$model" = "F018" ]; then
            log_echo "model is: $model, master set cam restart"
	    echo 1 > /sys/class/gpio/gpio210/value
	    sleep 1.0
            echo 0 > /sys/class/gpio/gpio210/value
        fi
    ;;

    *)
        echo "unsupport operation!"
        help
    ;;
    esac

else
    help
    exit 1
fi
