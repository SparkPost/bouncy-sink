#!/usr/bin/env python3
from __future__ import print_function
import subprocess
from datetime import datetime

# -----------------------------------------------------------------------------------------
# Main code
# -----------------------------------------------------------------------------------------

# 0=Mon, ... 7=Sun. Make a specific days worse / better than the others.
weekday_bounce_rate = [4, 12, 6, 2, 4, 4, 4]
t = datetime.utcnow()
today_bounce_rate = weekday_bounce_rate[t.weekday()]
print('Today\'s bounce rate is', today_bounce_rate)

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

