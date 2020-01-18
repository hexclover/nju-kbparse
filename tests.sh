#!/bin/bash
prog="./kbparse.py"
[ -z "$key" ] && read key

make clean
echo $key | $prog -h
echo $key | $prog -o -
echo $key | $prog -o testcase_csv.csv -w 10
echo $key | $prog -o testcase_ics.ics -w 10
echo $key | $prog -o - -f csv
echo $key | $prog -o - -f ics
$prog -o - -k $key
echo $key | $prog -t 20191 -w 5,6,7,10,16,17-20
echo $key | $prog -f csv -t 20192 -w 1-18
echo $key | $prog -t 20293
echo $key | $prog -f ics -t 20192 -w 5,6-13,19
# RegEx
$prog -f ics -c 0000 -o - -k $key
echo $key | $prog -f ics -n 英 -o -
echo $key | $prog -o -n 形式 -c 0
