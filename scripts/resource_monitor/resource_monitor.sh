#!/bin/bash
# Resource monitoring tool for Cromwell.
# This script is for GCP backend only.

INTERVAL=$1
if [[ -z "$INTERVAL" ]]; then
  INTERVAL=10
fi

printf 'time\tmem\tdisk\tcpu_pct\n'

while true; do
  TIME=$(date +%s)
  MEM=$(free -b | awk 'NR==2{print $3}')
  DISK=$(df -B1 -P /cromwell_root | awk 'NR>1{sum+=$3}END{print sum}')
  # Using 'top' to get total cpu usage: usage = 100 - idle.
  # https://stackoverflow.com/questions/9229333/how-to-get-overall-cpu-usage-e-g-57-on-linux#comment33209786_9229692
  CPU_PCT=$(top -b -n2 -p 1 | grep -F '%Cpu' | tail -1 | awk -F 'id,' '{n=split($1,vs,","); v=vs[n]; sub(" ","",v); print 100.0-v}')
  printf '%d\t%d\t%d\t%.2f\n' "$TIME" "$MEM" "$DISK" "$CPU_PCT"
  sleep "$INTERVAL"
done
