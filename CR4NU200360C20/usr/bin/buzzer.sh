#!/bin/sh

#buzzer.sh 6 250000 125000 0.2 0.2 5
pwm_channel=$1
period=$2
duty_cycle=$3
run_time=$4
interval_duration=$5
count=$6

echo $pwm_channel > /sys/devices/platform/soc@3000000/2000c00.pwm/pwm/pwmchip0/export
echo $period > /sys/devices/platform/soc@3000000/2000c00.pwm/pwm/pwmchip0/pwm6/period
echo $duty_cycle > /sys/devices/platform/soc@3000000/2000c00.pwm/pwm/pwmchip0/pwm6/duty_cycle

for i in $(seq 1 $count); do
        echo 1 > /sys/devices/platform/soc@3000000/2000c00.pwm/pwm/pwmchip0/pwm6/enable
        sleep $run_time
        echo 0 > /sys/devices/platform/soc@3000000/2000c00.pwm/pwm/pwmchip0/pwm6/enable
        sleep $interval_duration
done

echo $pwm_channel > /sys/devices/platform/soc@3000000/2000c00.pwm/pwm/pwmchip0/unexport
