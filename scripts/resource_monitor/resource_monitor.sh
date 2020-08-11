#!/bin/bash
# Resource monitoring tool for Cromwell.
# This script is for GCP backend only.

INTERVAL=$1
if [[ -z "$INTERVAL" ]]; then
  INTERVAL=20
fi

printf 'time\tmem\tdisk\tcpu_pct\n'

while true; do
  # Seconds since epoch.
  TIME=$(date +%s)
  # -b for size in bytes.
  MEM=$(free -b | awk 'NR==2{print $3}')
  # -b for size in bytes.
  DISK=$(du -s -b /cromwell_root | awk '{print $1}')
  # Use top to get total cpu usage: usage = 100 - idle.
  # Use data from the 2nd iteration (top -n2 and tail -1) for better accuracy.
  # https://stackoverflow.com/questions/9229333/how-to-get-overall-cpu-usage-e-g-57-on-linux#comment33209786_9229692
  CPU_PCT=$(top -b -n2 -p1 | grep -F '%Cpu' | tail -1 | awk -F 'id,' '{n=split($1,vs,","); v=vs[n]; sub(" ","",v); print 100.0-v}')

  printf '%d\t%d\t%d\t%.2f\n' "$TIME" "$MEM" "$DISK" "$CPU_PCT"
  sleep "$INTERVAL"
done
