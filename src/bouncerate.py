#!/usr/bin/env python3
from __future__ import print_function
import subprocess
from datetime import datetime
from common import readConfig, baseProgName, createLogger

def nWeeklyCycle(d, t):
    cycle_len = len(d)
    assert cycle_len % 7 == 0
    nweeks = int(cycle_len / 7)
    year, week, day = t.isocalendar()
    odd_week_offset = (week % nweeks) * 7
    i = day-1 + odd_week_offset
    return d[i], i

# -----------------------------------------------------------------------------------------
# Main code
# -----------------------------------------------------------------------------------------

if __name__ == "__main__":
    logger = createLogger(baseProgName() + '.log', 10)
    try:
        t = datetime.utcnow()
        cfg = readConfig('consume-mail.ini')
        weekly_cycle_bounce_rate = cfg.get('Weekly_Cycle_Bounce_Rate', '3').split(',')
        today_bounce_rate, x = nWeeklyCycle(weekly_cycle_bounce_rate, t)
        logger.info('Today is day {} (zero based) in the {}-day cycle. Bounce rate will be {}%'.format(x, len(weekly_cycle_bounce_rate), today_bounce_rate))
        filename = '/etc/pmta/config'
        logger.info('Changing line of file', filename)
        with open(filename, "r+") as f:
            pmta_cfg = f.readlines()
            pmta_cfg_bounce_param = 'dummy-smtp-blacklist-bounce-percent'
            for i, s in enumerate(pmta_cfg):
                if pmta_cfg_bounce_param in s:
                    print(i, s)
                    pmta_cfg[i] = '{} {}\t# Updated by script {} on {} UTC\n'.format(pmta_cfg_bounce_param, today_bounce_rate, __file__, t.strftime('%Y-%m-%dT%H:%M:%S'))
            f.seek(0)
            f.writelines(pmta_cfg)
            f.truncate()
            res = subprocess.check_output(['sudo', 'pmta','reload'])
            logger.info(res)
    except Exception as e:
        logger.error(e)

    try:
        # Check where we are in cycle for resetting suppression list
        t = datetime.utcnow()
        weekly_cycle_supp = cfg.get('Weekly_Cycle_Suppressions_Purge', '0').split(',')
        today_supp_purge, x = nWeeklyCycle(weekly_cycle_supp, t)
        # Only do at midnight
        h = t.hour
        today_supp_purge = (int(today_supp_purge) > 0) and (h == 0)
        logger.info('Today is day {} (zero based) in the {}-day cycle. Hour = {}. Suppression purge = {}'.format(x, len(weekly_cycle_supp), h, today_supp_purge))
        if today_supp_purge:
            res = subprocess.run(['./suppression_cleanup.sh'], shell=True)
            logger.info(res)
    except Exception as e:
        logger.error(e)



