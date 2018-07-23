#!/usr/bin/env python3
# simple tool to check output from same functions as web reporting uses
from webReporter import Results
import json

shareRes = Results()
m = shareRes.getArrayResults('ts_', 'messages')
print(json.dumps(m))

