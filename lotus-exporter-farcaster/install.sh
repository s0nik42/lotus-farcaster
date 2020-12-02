#!/bin/bash
IUSER="$1"
PROMETHEUS_NODE_EXPORTER_FOLDER="/var/lib/prometheus/node-exporter/" # DEFAULT UBUNTU LOCATION
EXEC_PATH="$(dirname $0)"

if [ "$(id -u)" -ne 0 ]
then
	echo "ERROR: must be run as root"
elif [ -z "$IUSER" ]
then
	echo "Usage: $0 LOTUS_USER_NAME"
elif [ ! "$(id $IUSER)" ]
then
	echo "ERROR: user $IUSER doesn't exist"
elif [ ! -f "$(getent passwd $IUSER | cut -d: -f6)/.lotus/config.toml" ]
then
	echo "ERROR: user $IUSER doesn't seems to be a lotus user $(getent passwd $IUSER | cut -d: -f6)/.lotus/config.toml doesn't exist"
else
	echo -e "\nInstalling required debian packages : "
	echo "------------------------------------- "
	apt install python3-toml prometheus-node-exporter
	echo -e "\nFinishing installation : "
	echo "----------------------- "
	set -x
	cp "$EXEC_PATH/lotus-exporter-farcaster.py" "/usr/local/bin"
	chown "$IUSER" "$EXEC_PATH/lotus-exporter-farcaster.py"
	chmod +x "$EXEC_PATH/lotus-exporter-farcaster.py"
	chmod g+r "$PROMETHEUS_NODE_EXPORTER_FOLDER"
	chgrp "$IUSER" "$PROMETHEUS_NODE_EXPORTER_FOLDER"
	cat "$EXEC_PATH/lotus-exporter-farcaster.cron" |sed "s/LOTUS_USER/$IUSER/" > "/etc/cron.d/lotus-exporter-farcaster"
	set +x
	cat << EOF 

FARCASTER INSTALLATION COMPLETED

********************************************************************************

TESTING : 
	curl -s -o - http://localhost:9100/metrics -s |grep "lotus_info"

OUTPUT (something like) :
lotus_daemon_info{miner_id="f010479",network="mainnet",version="1.1.2+git.d4cdc6d33"} 6

TROUBLESHOOTING :
	1/ Wait, it can take up to 1min for information to get polled. 
	2/ Look at /var/log/syslog

NEXT STEPS : 
  - Add this node to your prometheus server
  - Add the farecaster dashboard to grafana (import through ui)

********************************************************************************
EOF
	exit 0
fi
exit 1
