#!/usr/bin/env python3
#
# Web reporting and access functions for shared data held in Redis
# Expects to be run in main project directory, i.e, resources in relative path ./templates
import os, redis, json
from flask import Flask, make_response, render_template, request, send_file
app = Flask(__name__)

appName = 'consume-mail'
# Access to Redis data
def getResult(k):
    redisUrl = os.getenv('REDIS_URL', default='localhost')          # Env var is set by Heroku; will be unset when local
    r = redis.from_url(redisUrl, socket_timeout=5)                  # shorten timeout so doesn't hang forever
    rkeyPrefix = appName + ':' + os.getenv('RESULTS_KEY', default='0') + ':'    # allows unique app instances if needed (e.g. Heroku)
    res = r.get(rkeyPrefix + k)
    if res:
        return res
    else:
        return None

# returns True if data written back to Redis OK.  d is a dict of key-value pairs to write
def setResults(d):
    redisUrl = os.getenv('REDIS_URL', default='localhost')          # Env var is set by Heroku; will be unset when local
    r = redis.from_url(redisUrl, socket_timeout=5)                  # shorten timeout so doesn't hang forever
    rkeyPrefix = appName + ':' + os.getenv('RESULTS_KEY', default='0') + ':'    # allows unique app instances if needed (e.g. Heroku)
    ok = True
    for k, v in d.items():
        ok = ok and r.set(rkeyPrefix + k, v)
    return ok                                                       # true iff all the writes were ok

def getMatchingResults():
    redisUrl = os.getenv('REDIS_URL', default='localhost')          # Env var is set by Heroku; will be unset when local
    r = redis.from_url(redisUrl, socket_timeout=5)                  # shorten timeout so doesn't hang forever
    rkeyPrefix = appName + ':' + os.getenv('RESULTS_KEY', default='0') + ':'    # allows unique app instances if needed (e.g. Heroku)
    res = {'startedRunning': 'Not yet - waiting for scheduled running to begin'}       # default data
    for k in r.scan_iter(match=rkeyPrefix+'*'):
        v = r.get(k).decode('utf-8')
        idx = k.decode('utf-8') [len(rkeyPrefix):]                  # strip the prefix
        res[idx] =  v                                               # everything is a string at this point
    return res

def incrementKey(k):
    print('Stub: incrementing ', k)
    return True

# Flask entry points
@app.route('/', methods=['GET'])
def status_html():
    r = getMatchingResults()
    # pass in merged dict as named params to template substitutions
    res = render_template('index.html', **r, jsonUrl=request.url+'json')
    return res

# This entry point returns JSON-format report on the traffic generator
@app.route('/json', methods=['GET'])
def status_json():
    r = getMatchingResults()
    flaskRes = make_response(json.dumps(r))
    flaskRes.headers['Content-Type'] = 'application/json'
    return flaskRes

@app.route('/favicon.ico')
def favicon():
    return send_file('favicon.ico', mimetype='image/vnd.microsoft.icon')

# Start the app
if __name__ == "__main__":
    app.run()
