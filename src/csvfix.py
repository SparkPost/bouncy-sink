#!/usr/bin/env python3
# Fix up ragged columns to work around problem https://github.com/wireservice/agate/issues/666
import sys, csv
max_sniff_lines = 1000
sniff_buf = []

def columns_in(l):
    split_l = list(csv.reader(l.splitlines()))              # list, 0th entry holds content
    return len(split_l[0])

def max_columns_in(buf):
    max_c = 0
    for i in buf:
        max_c = max(columns_in(i), max_c)
    return max_c

def emit(buf, max_c):
    for i in buf:
        this_c = columns_in(i)
        assert this_c <= max_c
        pad = ',' * (max_c - this_c)
        print('{}{}'.format(i, pad))

with sys.stdin as f:
    sniffDone = False
    for line in f:
        line = line.rstrip()                # remove trailing whitespace including line break
        if len(sniff_buf) <= max_sniff_lines:
            sniff_buf.append(line)
        elif not sniffDone:
            # decide, emit the sniff buffer, keep rolling
            max_c = max_columns_in(sniff_buf)
            emit(sniff_buf, max_c)
            sniffDone = True
        else:
            emit([line], max_c)

if sniff_buf and not sniffDone:
    # short files didn't fill/empty the sniff buffer - decide & emit them now
    max_c = max_columns_in(sniff_buf)
    emit(sniff_buf, max_c)
