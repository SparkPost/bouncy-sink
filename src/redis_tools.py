#!/usr/bin/env python3
# https://gist.github.com/dchaplinsky/7985473 with some cleanup

import os, sys, redis, argparse, json

redisHost, redisPort = os.getenv('REDIS_URL', default='localhost:6379').split(':')
redis_client = redis.Redis(host=redisHost, port=redisPort)
print('Opened redis connection to {} port {}'.format(redisHost, redisPort))

PARSER = argparse.ArgumentParser(
    description='Dump/Load key-value data from redis by wildcard')

PARSER.add_argument('--wildcard',
                    dest="wildcards",
                    help="Wildcard for keys to dump",
                    action='append')

PARSER.add_argument('operation',
                    choices=['dump', 'load'],
                    help="dump or load")

PARSER.add_argument('filename', help="Filename")

ARGS = PARSER.parse_args()

if ARGS.operation == "dump":
    data = {}
    total_count = 0
    for w in ARGS.wildcards:
        for key in redis_client.scan_iter(w):
            v = redis_client.get(key).decode('utf8')            # Put everything back into UTF-8 chars for JSON
            k = key.decode('utf8')
            data[k] = v
            total_count += 1
            if total_count % 100 == 0:
                print('.', end='', flush=True)                  # progress marker
    print('\n')

    print("Got %s keys from redis. Saving to the file..." % total_count)
    with open(ARGS.filename, "w") as fp:
        json.dump(data, fp, indent="    ", sort_keys=True)
    print("Saving of %s is done" % ARGS.filename)

elif ARGS.operation == "load":
    with open(ARGS.filename, "r") as fp:
        data = json.load(fp)

    assert isinstance(data, dict)

    pipe = redis_client.pipeline()
    print("Got %s keys from file. Saving to redis..." % len(data.keys()))

    for k, v in data.items():
        pipe.set(k, v)
    pipe.execute()
    print("Saved")