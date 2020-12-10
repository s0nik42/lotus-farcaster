#!/bin/bash
#@author: s0nik42
#Copyright (c) 2020 Julien NOEL (s0nik42)
#
#MIT License
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.

IUSER="$1"
PROMETHEUS_NODE_EXPORTER_FOLDER="/var/lib/prometheus/node-exporter/" # DEFAULT UBUNTU LOCATION
EXEC_PATH="$(dirname $0)"

OK="[\033[0;32m OK \033[0m]"
KO="[\033[0;31m KO \033[0m]"

if [ "$(id -u)" -ne 0 ]
then
	echo -e "$KO : must be run as root"
    exit 1
elif [ -z "$IUSER" ]
then
	echo "Usage: $0 LOTUS_USER_USERNAME"
    exit 1
fi

echo -n "Check if $IUSER exist : "
if [ ! "$(id $IUSER 2>/dev/null)" ]
then
	echo -e "$KO user $IUSER doesn't exist"
    exit 1
fi
echo -e "$OK"

echo -n "Check if $IUSER is a lotus user : "
if [ ! -f "$(getent passwd $IUSER | cut -d: -f6)/.lotus/config.toml" ]
then
	echo -e "$KO user $IUSER doesn't seems to be a lotus user $(getent passwd $IUSER | cut -d: -f6)/.lotus/config.toml doesn't exist"
    exit 1
fi
echo -e "$OK"

echo -n "Check if lotus-exporter-farcaster.py run properly : "
r=$(sudo -u "$IUSER" /usr/local/bin/lotus-exporter-farcaster.py)
if [ $(echo "$r" | grep -c 'lotus_scrape_execution_succeed { } 1') -eq 0 ]
then
    echo -e "$KO error encountered : "
    echo "$r" | tail -10 | while read a
    do
        echo -e "\t $a"
    done
    echo "TODO : run manually : sudo -u "$IUSER" /usr/local/bin/lotus-exporter-farcaster.py"
    exit 1
fi
echo -e "$OK"

echo -n "Check if $IUSER has write access to $PROMETHEUS_NODE_EXPORTER_FOLDER : "
r=$(sudo -u $IUSER sh -c "if [ -w $PROMETHEUS_NODE_EXPORTER_FOLDER ] ; then echo 1; else echo 0; fi")
if [ $r -eq 0 ]
then
    echo -e "$KO Cannot right to folder $PROMETHEUS_NODE_EXPORTER_FOLDER"
    echo "TODO :" 
    echo "  Option 1/ rerun the install script OR"
    echo "  Option 2/ manually give right permission to $IUSER to $PROMETHEUS_NODE_EXPORTER_FOLDER"
    exit 1
fi
echo -e "$OK"

echo -n "Check if metrics are exposed in $PROMETHEUS_NODE_EXPORTER_FOLDER : "
if [ ! -f "$PROMETHEUS_NODE_EXPORTER_FOLDER/farcaster.prom" ]
then
    echo -e "$KO metrics not found in $PROMETHEUS_NODE_EXPORTER_FOLDER."
    echo "TODO : lotus-exporter-farcaster is spawned every minute. you may wait. If it doens't work after 2 minutes. You fall under an unknow error. Look /var/log/syslog for troubleshooting"
    exit 1
fi
echo -e "$OK"

echo -n "Check if $PROMETHEUS_NODE_EXPORTER_FOLDER/farcaster.prom is owned by $IUSER : "
AUSER=$( stat -c '%U' "$PROMETHEUS_NODE_EXPORTER_FOLDER/farcaster.prom" )
if [ "$AUSER" != "$IUSER" ]
then
   echo -e "$KO $PROMETHEUS_NODE_EXPORTER_FOLDER/farcaster.prom doesnt belong to $IUSER but ($AUSER) "
   echo "TODO: Remove $PROMETHEUS_NODE_EXPORTER_FOLDER/farcaster.prom and try again"
   exit 1
fi
echo -e "$OK"

echo -n "Check if $PROMETHEUS_NODE_EXPORTER_FOLDER/farcaster.prom creation date : "
r=$(expr `date +%s` - `stat -L --format %Y "$PROMETHEUS_NODE_EXPORTER_FOLDER/farcaster.prom"`)
if [ "$r" -gt 90 ]
then
    echo -e "$KO file is too old ($r seconds). it as not been updated withing the last 90 secs"
    echo "TODO: look at /var/log/syslog for troubleshooting"
    exit 1
fi

echo -n "Check if prometheus-node-exporter is running properly : "
r=$(curl -s -o - http://localhost:9100/metrics |wc -l 2>/dev/null)
if [ "$r" -eq 0 ]
then
    echo -e "$KO cannot connect to prometheus-node-exporter (cannot access to http://localhost:9100/metrics)"
    echo "TODO : Install and start prometheus-node-exporter and run farcaster install.sh again"
    exit 1
fi
echo -e "$OK"

echo -n "Check for farcaster data in prometheus-node-exporter : "
r=$(curl -s -o - http://localhost:9100/metrics |grep "lotus_info")
if [ "$?" -ne 0 ]
then
    echo -e "$KO Cannot find lotus data in prometheus-node-exporter"
    exit 1
fi
echo -e "$OK"

echo -e "\033[0;33m"
cat <<EOF
 ________________________________
/ All good, the node is properly \ 
\ configured. !!!                /
 --------------------------------
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\ 
                ||----w |
                ||     ||
EOF
echo -e "\033[0m"
