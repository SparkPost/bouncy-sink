#!/usr/bin/env python3
#
# Web reporting and access functions for shared data held in Redis
# Expects to be run in main project directory, i.e, resources in relative path ./templates
import os, redis, json
from flask import Flask, make_response, render_template, request, send_file
app = Flask(__name__)

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

    def getMatchingResults(self):
        res = {}
        for k in self.r.scan_iter(match=self.rkeyPrefix+'*'):
            v = self.r.get(k).decode('utf-8')
            idx = k.decode('utf-8') [len(self.rkeyPrefix):]             # strip the app prefix
            if idx.startswith('int_'):
                idx= idx[len('int_'):]                                  # strip the pseudo-type prefix
                res[idx] =  int(v)                                      # use as int
            else:
                res[idx] =  v                                           # use as string
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

# Flask entry points
@app.route('/', methods=['GET'])
def status_html():
    shareRes = Results()                                            # class for sharing summary results
    r = shareRes.getMatchingResults()
    if not r:
        r = {'startedRunning': 'Not yet - waiting for scheduled running to begin'}       # default data
    # pass in merged dict as named params to template substitutions
    res = render_template('index.html', **r, jsonUrl=request.url+'json')
    return res

# This entry point returns JSON-format report on the traffic generator
@app.route('/json', methods=['GET'])
def status_json():
    shareRes = Results()                                            # class for sharing summary results
    r = shareRes.getMatchingResults()
    flaskRes = make_response(json.dumps(r))
    flaskRes.headers['Content-Type'] = 'application/json'
    return flaskRes

@app.route('/favicon.ico')
def favicon():
    return send_file('favicon.ico', mimetype='image/vnd.microsoft.icon')

# Start the app
if __name__ == "__main__":
    app.run()
