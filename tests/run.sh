#!/bin/sh
# Runs every tests/*.sh except this file.
for t in tests/*.sh; do
  [ "$t" = "tests/run.sh" ] && continue
  sh "$t" || { echo "FAILED $t"; exit 1; }
done
echo "all tests passed"
