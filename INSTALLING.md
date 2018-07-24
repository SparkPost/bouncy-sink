# Bouncy Sink configuration

The Bouncy Sink is based on PMTA, with specific "blackhole" configuration used bounce some traffic with realistic in-band bounce
codes. The other sink actions are handled by a script that is scheduled by `cron` to run once a minute.

## Pre-requisites

Host capable of running PMTA 4.x
- Host has TCP port 25 open to inbound traffic
- git command line
- PMTA install file + 4.x license

# Example installation - with Amazon EC2 Linux

## PowerMTA

```
sudo su -
sudo rpm -Uvh PowerMTA-4.5r13-201803291724.x86_64.rpm 

# remove sendmail which otherwise tries to grab port 25
service sendmail stop
sudo chkconfig sendmail off

# make a directory to receive inbound mail
sudo mkdir /var/spool/mail/inbound
```

Get this project:
```
cd ~
git clone https://github.com/SparkPost/bouncy-sink.git
cd bouncy-sink
```

Copy example PMTA config file & blacklist.dat 

```
sudo cp etc/pmta/ /etc/pmta/
vim /etc/pmta/config
```
Customise `postmaster`, `smtp-listener`, `dummy-smtp-ip` settings to suit your environment.  Check PMTA starts
```
sudo service pmta start
```

Set up DNS entries to map inbound domains to your host IP addresses.
Send in some mail, check it arrives in the `inbound` spool directory.
You now have a functioning PowerMTA.

## Python + libraries, redis
Get an up-to-date Python interpreter (and `pip`) and git.  
```
sudo su -
yum install -y python36 python36-pip git
```

Set path for `pip` by editing .profile and adding
```
export PATH=/usr/local/bin:$PATH
```

Upgrade pip to latest version
```
pip install --upgrade pip
```

Get libraries:
```
pip install redis gunicorn flask flask_cors dnspython 
```

Get redis - see https://redis.io/topics/quickstart and https://unix.stackexchange.com/a/108311
```
yum install -y gcc
wget http://download.redis.io/redis-stable.tar.gz
tar xvzf redis-stable.tar.gz
cd redis-stable/deps
make hiredis jemalloc linenoise lua geohash-int
cd ..
make install
yum install -y tcl
make test
```
If using EC2 Linux,[this guide](https://medium.com/@andrewcbass/install-redis-v3-2-on-aws-ec2-instance-93259d40a3ce)
will help - start from the "Make directories & copy files" stage onwards.

Check you've started the `redis` service using this command. It should say PONG back.
```
redis-cli ping
```

Run the Python script manually using 
```
sudo src/consume-mail.py /var/spool/mail/inbound/
```

Set up crontab to run script. The easiest way to do this is `crontab -e` then paste in the contents of `cronfile` from the project.

The crontab launches gunicorn web server and the script in "forever" mode on reboot. To start it without rebooting, copy the line
into an interactive shell.

## Gunicorn
Gunicorn serves web pages on the port specificed in cronfile
Gunicorn access logfile is in `/var/log/gunicorn.log`.
