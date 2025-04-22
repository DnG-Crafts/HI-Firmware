#!/bin/sh

# MCU pwr en
MCU_PWR_EN=""

gpio_get()
{
    local board=$(get_sn_mac.sh board) 
    case $board in
         "CR4NU200360C23")
	    # SOC: PE12 --> PIN: 140
             echo "140" 
             ;;
         *)
             echo ""
             ;;
    esac
}

gpio_export()
{
    [ -L /sys/class/gpio/gpio$MCU_PWR_EN ] || echo $MCU_PWR_EN > /sys/class/gpio/export
}

gpio_unexport()
{
    [ -L /sys/class/gpio/gpio$MCU_PWR_EN ] && echo $MCU_PWR_EN > /sys/class/gpio/unexport
}

gpio_init()
{
    echo out > /sys/class/gpio/gpio$MCU_PWR_EN/direction
    # 0: power on; 1: power off
    echo 0 > /sys/class/gpio/gpio$MCU_PWR_EN/value
}

gpio_uninit()
{
    # 0: power on; 1: power off
    echo 1 > /sys/class/gpio/gpio$MCU_PWR_EN/value
}

pwr_rst()
{
    echo 1 > /sys/class/gpio/gpio$MCU_PWR_EN/value
    sleep 1
    echo 0 > /sys/class/gpio/gpio$MCU_PWR_EN/value
}

help()
{
    echo "Usage: $0 [enable|disable]"
}


MCU_PWR_EN=$(gpio_get)

if [ x"$MCU_PWR_EN" == x ]; then
    echo "MainBoard does not support MCU reset"
    exit 0
fi

if [ $# -eq 1 ]; then

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
elif [ $# -eq 0 ]; then 
    pwr_rst
else
    help
    exit 1
fi
