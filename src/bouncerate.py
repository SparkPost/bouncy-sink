#!/usr/bin/env python3
from __future__ import print_function
import subprocess
from datetime import datetime

# -----------------------------------------------------------------------------------------
# Main code
# -----------------------------------------------------------------------------------------

# 0=Mon, ... 7=Sun. Make a specific days worse / better than the others. Really hit Tuesdays hard
#         weeks:       even                   odd
weekday_bounce_rate = [4, 40, 40, 2, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
assert len(weekday_bounce_rate) == 14
t = datetime.utcnow()
year, week, day = t.isocalendar()
odd_week_offset = (week % 2) * 7
d = day-1 + odd_week_offset
today_bounce_rate = weekday_bounce_rate[d]
print('Today is day {} (zero based) in the {}-day cycle. Bounce rate will be {}%'.format(d, len(weekday_bounce_rate), today_bounce_rate))

filename = '/etc/pmta/config'
print('Changing line of file', filename)
with open(filename, "r+") as f:
    cfg = f.readlines()
    cfg_bounce_param = 'dummy-smtp-blacklist-bounce-percent'
    for i, s in enumerate(cfg):
        if cfg_bounce_param in s:
            print(i, s)
            cfg[i] = '{} {}\t# Updated by script {} on {} UTC\n'.format(cfg_bounce_param, today_bounce_rate, __file__, t.strftime('%Y-%m-%dT%H:%M:%S'))
    f.seek(0)
    f.writelines(cfg)
    f.truncate()

res = subprocess.run(['sudo', 'pmta','reload'], check=True)

