#!/usr/bin/env python3
# simple tool to check output from same functions as web reporting uses
from webReporter import Results, list_of_dicts_merge
import json

shareRes = Results()
m = shareRes.getArrayResults('ts_', 'messages')
p = shareRes.getArrayResults('ps_', 'processes')
c = list_of_dicts_merge(m, p, 'time', {'messages': 0}, {'processes': 0})  # merge two time-series together
print(json.dumps(c))

