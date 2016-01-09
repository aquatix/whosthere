whosthere
---------

Determine who is or was online on your network by keeping track of SNMP info from your router.

For example, the following one-liner gets the relevant information from my DD-WRT running LinkSys router:

```bash
#!/bin/bash
snmpwalk -c public -v 1 192.168.1.1 | grep iso.3.6.1.2.1.3.1.1.2.0.1 | cut -c27- | sed -s "s/Hex-STRING: //" | awk -v date="$(date +"%Y-%m-%d %H:%M:%S ")" '$0=date$0' >> /var/log/whosthere/mynetwork_$(date +"%Y%m%d").log
```

The lines then look like this:

```
2016-01-09 00:00:01 128.126.6.1 = XX 00 00 00 00 06 
2016-01-09 00:00:01 192.168.1.115 = XX 5F F4 61 08 22 
2016-01-09 00:00:01 192.168.1.203 = XX 5A F7 82 EC 7F 
2016-01-09 00:00:01 192.168.1.215 = XX 20 0C 74 88 3B 
2016-01-09 00:00:01 192.168.1.225 = XX 50 E6 2D C6 CE 
2016-01-09 00:00:01 192.168.1.226 = XX 04 20 1E 95 75 
2016-01-09 00:00:01 192.168.1.231 = XX 24 9B 0C 3F 65 
2016-01-09 00:00:01 192.168.1.232 = XX 7A 88 50 F6 9E 
2016-01-09 00:00:01 192.168.1.233 = XX 04 4B 2F 95 CE 
2016-01-09 00:01:01 128.126.6.1 = XX 00 00 00 00 06 
2016-01-09 00:01:01 192.168.1.115 = XX 5F F4 61 08 22 
2016-01-09 00:01:01 192.168.1.203 = XX 5A F7 82 EC 7F 
2016-01-09 00:01:01 192.168.1.215 = XX 20 0C 74 88 3B 
2016-01-09 00:01:01 192.168.1.225 = XX 50 E6 2D C6 CE 
2016-01-09 00:01:01 192.168.1.226 = XX 04 20 1E 95 75 
2016-01-09 00:01:01 192.168.1.231 = XX 24 9B 0C 3F 65 
2016-01-09 00:01:01 192.168.1.232 = XX 7A 88 50 F6 9E 
2016-01-09 00:01:01 192.168.1.233 = XX 04 4B 2F 95 CE 
```

To make sense from this all, run the parser with:

```
python whosthere.py parselogs --logdir=. --prefix=mynetwork --macfile=/home/myuser/.dot/privdotfiles/stuff/mynetwork_client_macs.txt

or:

python whosthere.py parselogs --logdir=/var/log/whosthere --prefix=mynetwork --macfile=/home/myuser/workspace/mynetwork_client_macs.txt
```
