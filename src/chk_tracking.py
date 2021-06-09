#!/usr/bin/env python3
# simple tool to check status of tracking domains
import os, json, redis

def get_array(r, ts_pfx):
    for k in r.scan_iter(match=ts_pfx+'*'):
        v = r.get(k).decode('utf-8')
        ttl = r.ttl(k)
        print('{},{},EX={}'.format(k.decode('utf-8'), v, ttl))


redisUrl = os.getenv('REDIS_URL', default='redis://localhost')      # Env var is set by Heroku; will be unset when local
redis_client = redis.from_url(redisUrl, socket_timeout=5)                 # shorten timeout so doesn't hang forever
print('Opened redis connection to {}'.format(redis_client))
get_array(redis_client, 'http')

