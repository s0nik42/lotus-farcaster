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


help_message () {
      echo "Usage : $(basename $0) [ -c folder ] LOTUS_PROCESS_USERNAME
    Install lotus-exporter-farcaster. 

    This script will check if all the component of the lotus-exporter-farcaster
    stack are working properly

    IMPORTANT : This exporter must be install on the same machine as the 
    lotus-miner. You don't need it to be deployed to any other server like 
    (fullnode / markets node) 

    LOTUS_PROCESS_USERNAME : username of the linux user owning the lotus-miner 
    process the server.

    This script must be run as root

    Options:
      -c folder   specify the target configutation file location for 
                  lotus-exporter-farcaster. This option is useful in case 
                  multiple miners run on the same server. 
                  Default : ~LOTUS_PROCESS_USERNAME/.lotus-exporter-farcaster
                  "
}

# INTERNAL VARIABLES
PROMETHEUS_NODE_EXPORTER_FOLDER="/var/lib/prometheus/node-exporter/" # DEFAULT UBUNTU LOCATION
EXEC_PATH="$(dirname $0)"

# STATUS PRETTY PRINT DECLARATION
OK="[\033[0;32m OK \033[0m]"
KO="[\033[0;31m KO \033[0m]"
WARN=" [\033[0;33mWARN\033[0m]"

# CHECK SCRIPT OPTIONS
while getopts ":c:v?" opt; do
  case $opt in
    c)
        CUSTOM_CONFIG_ARG="-c" >&2
        CUSTOM_CONFIG_PATH="$OPTARG" >&2
      ;;
    [\?v])
      echo "Invalid option: -$OPTARG" >&2
      help_message
      exit 1
      ;;
    :)
      echo "Option -$OPTARG requires an argument." >&2
      exit 1
      ;;
  esac
done
shift $(($OPTIND - 1))

# DISPLAY USAGE IS NO PARAMETERS
if [ $# -eq 0 ];
then
    help_message
    exit 0
fi

# SET USERNAME
IUSER="$1"

# RETRIEVE USER HOME
if [ -n "$IUSER" ]
then
    IUSER_HOME=$(getent passwd -- "$IUSER" | cut -d: -f6)
else
    echo -e $KO 
    exit 1
fi


# RUN CHECKS
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

echo -n "Check if lotus-exporter-farcaster.py run properly : "
if [ -z "$CUSTOM_CONFIG_ARG" ]
then
    r=$(sudo -u "$IUSER" /usr/local/bin/lotus-exporter-farcaster.py)
else
    r=$(sudo -u "$IUSER" /usr/local/bin/lotus-exporter-farcaster.py "$CUSTOM_CONFIG_ARG" "$CUSTOM_CONFIG_PATH")
fi
if [ $(echo "$r" | grep -c 'lotus_scrape_execution_succeed {  } 1') -eq 0 ]
then
    echo -e "$KO error encountered : "
    echo "$r" | while read a
    do
        echo -e "\t $a"
    done
    echo "TODO : run manually : sudo -u "$IUSER" /usr/local/bin/lotus-exporter-farcaster.py" "$CUSTOM_CONFIG_ARG" "$CUSTOM_CONFIG_PATH" --debug
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
for i in {1..5}; do
    if [ ! -f "$PROMETHEUS_NODE_EXPORTER_FOLDER/farcaster.prom" ]
    then
        if [ "$i" -eq 5 ]
        then
            echo -e "$KO file doesn't exist"
            echo "TODO : lotus-exporter-farcaster is spawned every minute. you may wait. If it doens't work after 2 minutes. You fall under an unknow error. Look /var/log/syslog for troubleshooting"
            echo "You can rerun the check script directly : ./check -h"
            exit 1
        fi
        echo -e "$WARN attempt $i/5 : metrics not found in $PROMETHEUS_NODE_EXPORTER_FOLDER."
        echo "lets retry in 30sec..."
        sleep 30
    else
        echo -e "$OK"
        break
    fi
done
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
for i in {1..5}; do
    r=$(expr `date +%s` - `stat -L --format %Y "$PROMETHEUS_NODE_EXPORTER_FOLDER/farcaster.prom"`)
    if [ "$r" -gt 90 ]
    then
        if [ "$i" -eq 5 ]
        then
            echo -e "$KO file is to old"
            echo "TODO: look at /var/log/syslog for troubleshooting"
            echo "You can rerun the check script directly : ./check -h"
            exit 1
        fi
        echo -e "$WARN attempt $i/5 : file is too old ($r seconds). it as not been updated withing the last 90 secs"
        echo "lets retry in 30sec..."
        sleep 30
    else
        echo -e "$OK"
        break
    fi
done

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
for i in {1..5}; do
    r=$(curl -s -o - http://localhost:9100/metrics |grep "lotus_info")
    if [ "$?" -ne 0 ]
    then
        if [ "$i" -eq 5 ]
        then
            echo -e "$KO Cannot find lotus data in prometheus-node-exporter"
            exit 1
        fi
        echo -e "$WARN attempt $i/5 : cannot find lotus_info in prometheus-node-exporter"
        echo "lets retry in 5sec..."
        sleep 5
    else
        echo -e "$OK"
        break
    fi
done

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
