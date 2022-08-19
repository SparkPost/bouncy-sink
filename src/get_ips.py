#!/usr/bin/env python3
import sys, csv
from tarfile import RECORDSIZE

header='type,timeLogged,timeQueued,orig,rcpt,orcpt,dsnAction,dsnStatus,dsnDiag,dsnMta,bounceCat,srcType,srcMta,dlvType,dlvSourceIp,dlvDestinationIp,dlvEsmtpAvailable,dlvSize,vmta,jobId,envId,queue,vmtaPool,header_x-sp-subaccount-id,header_x-sp-message-id,repSourceIp,feedbackType,format,userAgent,reportingMta,reportedDomain,header_From,header_Return-Path,header_X-job,header_Subject,rcvSourceIp,rcvSourceIp,dsnReportingMta'
header_t = header.split(',')

class DictObj:
    def __init__(self, in_dict:dict):
        assert isinstance(in_dict, dict)
        for key, val in in_dict.items():
            if isinstance(val, (list, tuple)):
                setattr(self, key, [DictObj(x) if isinstance(x, dict) else x for x in val])
            else:
                setattr(self, key, DictObj(val) if isinstance(val, dict) else val)


fh = csv.DictReader(sys.stdin)
# Force the fieldnames, as we may be feeding this program via "tail -f" so it might not see the line 1 header
fh.fieldnames = header_t

# Pre-initialise with known ones in order
ips = [
    '172.31.4.96',
    '172.31.15.167',
    '172.31.13.191',
    '172.31.9.210',
    '172.31.14.43',
    '172.31.4.19',
    '172.31.6.243',
]

for row in fh:
    r = DictObj(row)
    if r.type == 'd':
        # Delivery record
        try:
            i = ips.index(r.dlvSourceIp)
        except:
            ips.append(r.dlvSourceIp)
            i = ips.index(r.dlvSourceIp)

        print('{},{},{}{}'.format(r.timeLogged,r.vmta,','*i, r.dlvSourceIp))