#!/usr/bin/env bash
echo "Searching files for unique sending domains:"
for i in consume-mail.log*
do
    echo "$i:"
    # fix up file lines to be the same length, extract column 8 (sending domain), dedup, and show only lines with email addrs
    cat $i | src/csvfix.py |  grep "\.msg" | csvcut -c 7 | sort | uniq | grep "@"
done