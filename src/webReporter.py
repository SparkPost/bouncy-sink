#!/usr/bin/env python3
#
# Web reporting and access functions for shared data held in Redis
# Expects to be run in main project directory, i.e, resources in relative path ./templates
#
# Author: Steve Tuck.  (c) 2018 SparkPost
#
# Pre-requisites:
#   pip3 install flask, redis, flask-cors
#
import os, redis, json
from flask import Flask, make_response, render_template, request, send_file
from datetime import datetime, timezone
from flask_cors import CORS, cross_origin
app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

def timeStr(t):
    utc = datetime.fromtimestamp(t, timezone.utc)
    return datetime.isoformat(utc, sep='T', timespec='seconds')

class Results():
    def __init__(self):
        # Set up a persistent connection to redis results
        appName = 'consume-mail'
        redisUrl = os.getenv('REDIS_URL', default='localhost')              # Env var is set by Heroku; will be unset when local
        self.r = redis.from_url(redisUrl, socket_timeout=5)                 # shorten timeout so doesn't hang forever
        self.rkeyPrefix = appName + ':' + os.getenv('RESULTS_KEY', default='0') + ':'    # allows unique app instances if needed (e.g. Heroku)

    # Access to Redis data
    def getKey(self, k):
        res = self.r.get(self.rkeyPrefix + k)
        return res

    # returns True if data written back to Redis OK.  d is a dict of key-value pairs to write
    def setKey(self, k, v):
        ok = self.r.set(self.rkeyPrefix + k, v)
        return ok

    # collect basic metrics, i.e. started_running, and any keys prefixed int_
    def getMatchingResults(self):
        res = {'startedRunning': self.getKey('startedRunning').decode('utf-8') }
        int_pfx = self.rkeyPrefix + 'int_'
        for k in self.r.scan_iter(match=int_pfx+'*'):
            v = self.r.get(k).decode('utf-8')
            idx = k.decode('utf-8') [len(int_pfx):]                     # strip the app prefix
            res[idx] =  int(v)                                      # use as int
        return res

    # wrapper functions for integer type counters. Mark type in key name, as all redis objs are natively Bytes
    def incrementKey(self, k):
        self.r.incr(self.rkeyPrefix + 'int_' + k)

    def decrementKey(self, k):
        self.r.decr(self.rkeyPrefix + 'int_' + k)

    def getKey_int(self, k):
        v = self.r.get(self.rkeyPrefix + 'int_' + k)                    # force conversion on way out
        if v:
            v2 = v.decode('utf-8')
            return int(v2) if v2.isnumeric() else 0
        else:
            return 0

    def setKey_int(self, k, v):
        ok = self.r.set(self.rkeyPrefix + 'int_' + k, v)                # allow redis to set type on way in
        return ok

    def incrementTimeSeries(self, k):
        self.r.incr(self.rkeyPrefix + 'ts_' + k)

    def setPSTimeSeries(self, k, v):
        self.r.set(self.rkeyPrefix + 'ps_' + k, v)

    def getPSTimeSeries(self, k):                                       # return None if invalid or doesn't exist
        v = self.r.get(self.rkeyPrefix + 'ps_' + k)
        if v:
            v2 = v.decode('utf-8')
            return int(v2) if v2.isnumeric() else None
        else:
            return None

    def delTimeSeriesOlderThan(self, t):
        for i in ['ts_*', 'ps_*']:
            for k in self.r.scan_iter(match=self.rkeyPrefix + i):
                idx = k.decode('utf-8') [len(self.rkeyPrefix):]         # strip the app prefix
                ts = int(idx[len('ts_'):])                              # got the metric's timestamp as int
                if ts < t:
                    self.r.delete(k)

    def getArrayResults(self, pfx, keyName):
        ts_pfx = self.rkeyPrefix + pfx
        t = {}
        for k in self.r.scan_iter(match=ts_pfx+'*'):
            v = self.r.get(k).decode('utf-8')
            idx = k.decode('utf-8') [len(ts_pfx):]                      # strip the app prefix
            t[idx] = int(v)                                             # use as int
        res = []
        for key in t.keys():
            res.append( {'time' : timeStr(int(key)), keyName: t[key] } )
        return res


# Flask entry points
@app.route('/', methods=['GET'])
def status_html():
    shareRes = Results()                                            # class for sharing summary results
    r = shareRes.getMatchingResults()
    if not r:
        r = {'startedRunning': 'Not yet - waiting for scheduled running to begin'}       # default data
    # pass in merged dict as named params to template substitutions
    res = render_template('index.html', **r, thisUrl=request.url)
    return res

# This entry point returns JSON-format summary results report
@app.route('/json', methods=['GET'])
def status_json():
    shareRes = Results()                                            # class for sharing summary results
    r = shareRes.getMatchingResults()
    flaskRes = make_response(json.dumps(r))
    flaskRes.headers['Content-Type'] = 'application/json'
    return flaskRes

# Time-series of number of messages processed
@app.route('/json/ts-messages', methods=['GET'])
@cross_origin()
def json_ts_messages():
    shareRes = Results()
    r = shareRes.getArrayResults(pfx='ts_', keyName='messages')
    flaskRes = make_response(json.dumps(r))
    flaskRes.headers['Content-Type'] = 'application/json'
    return flaskRes

# Time-series of number of active processes
@app.route('/json/ts-processes', methods=['GET'])
@cross_origin()
def json_ts_processes():
    shareRes = Results()
    r = shareRes.getArrayResults(pfx='ps_', keyName='processes')
    flaskRes = make_response(json.dumps(r))
    flaskRes.headers['Content-Type'] = 'application/json'
    return flaskRes

@app.route('/favicon.ico')
def favicon():
    return send_file('favicon.ico', mimetype='image/vnd.microsoft.icon')

# Start the app
if __name__ == "__main__":
    app.run()
