# Cisco CUCM Jabber Stats
Script to get status of Jabber devices (CSF,TCT,TAB & BOT) via AXL and check for status of device in RisPort

### Requirements

* Tested only on Python 3.6+
* zeep
* influxdb
* lxml
* argparse

### Usage

Run from the commandline

```
python3 cisco_axl_jabber.py -ip 'CUCM_IP' -u 'CUCM_USERNAME' -p 'CUCM_PASSWORD' -v '12.0'
Breaking down into chunks: 4
Processing 1 batch...
Processing 2 batch...
Processing 3 batch...
Processing 4 batch...
Successfully captured current Risport status.
...
```

### Automate with PM2

Run from the commandline

```
pm2 start  cisco_axl_jabber.py --interpreter python3 --name jabber_status --cron '*/5 * * * *' --no-autorestart -- -ip 10.10.20.1 -u administrator -p ciscopsdt -v 12.0
```

### Useful PM2 commands

```
$ pm2 [list|ls|status]
$ pm2 flush
$ pm2 log
$ pm2 restart app_name
$ pm2 reload app_name
$ pm2 stop app_name
$ pm2 delete app_name
$ pm2 save or pm2 set pm2:autodump true
$ pm2 stop all
$ pm2 show <id|name>
$ pm2 startup
$ pm2 monit

```
[PM2 Quick Start](https://pm2.keymetrics.io/docs/usage/quick-start/)

### License

MIT
