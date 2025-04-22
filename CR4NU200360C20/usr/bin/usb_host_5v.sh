#!/bin/sh

# udisk 
# SOC: PG17 --> PIN: 209
# 0: power on; 1: power off
USB_P_EN1=209

# nozzle cam
# SOC: PG18 --> PIN: 210
# 0: power on; 1: power off
USB_P_EN2=210

gpio_export()
{
    [ -L /sys/class/gpio/gpio$USB_P_EN1 ] || echo $USB_P_EN1 > /sys/class/gpio/export
    [ -L /sys/class/gpio/gpio$USB_P_EN2 ] || echo $USB_P_EN2 > /sys/class/gpio/export
}

gpio_unexport()
{
    [ -L /sys/class/gpio/gpio$USB_P_EN1 ] && echo $USB_P_EN1 > /sys/class/gpio/unexport
    [ -L /sys/class/gpio/gpio$USB_P_EN2 ] && echo $USB_P_EN2 > /sys/class/gpio/unexport
}

gpio_init()
{
    echo out > /sys/class/gpio/gpio$USB_P_EN1/direction
    echo 0 > /sys/class/gpio/gpio$USB_P_EN1/value

    echo out > /sys/class/gpio/gpio$USB_P_EN2/direction
    echo 1 > /sys/class/gpio/gpio$USB_P_EN2/value
    sleep 1.0
    echo 0 > /sys/class/gpio/gpio$USB_P_EN2/value
}

gpio_uninit()
{
    echo 1 > /sys/class/gpio/gpio$USB_P_EN1/value
    echo 1 > /sys/class/gpio/gpio$USB_P_EN2/value
}

help()
{
    echo "Usage: $0 <enable|disable>"
}

if [ $# -eq 1 ]; then
    model=$(get_sn_mac.sh model)

    case $1 in
    "enable")
        gpio_export
        gpio_init
    ;;

    "disable")
        gpio_uninit
        gpio_unexport
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
