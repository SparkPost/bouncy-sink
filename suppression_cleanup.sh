#!/usr/bin/env bash
# Example showing how to purge entries
now=$(date +"%m_%d_%Y")
fn=purged_$now.csv
echo "Purging suppression list entries into $fn"
cd ../sparkySuppress/ && python3 ./sparkySuppress.py purge $fn