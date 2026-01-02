#!/bin/sh
ddcutil getvcp 10 2>/dev/null \
| awk -F'=' '{print $2}' \
| awk -F',' '{print int($1)}'
