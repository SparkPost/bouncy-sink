#!/usr/bin/env bash
cd /home/ec2-user/bouncy-sink/src; sudo /usr/local/bin/gunicorn webReporter:app --bind=0.0.0.0:8888 --access-logfile /var/log/gunicorn.log --daemon
