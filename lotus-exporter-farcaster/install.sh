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

    This script will check and propose to install all the requirements for the 
    exporter to work. It will also launch an assistant that autodetect the 
    miner configuration and test the configuration at the end.
    Each step can be skipped

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

    Debug:
      if you receive an error like:
		  ERROR: MinerGetBaseInfo returned no result
	then wait more than 900 epochs before your Power is >0 on chain
		  
		  "
}

# INTERNAL VARIABLES
PROMETHEUS_NODE_EXPORTER_FOLDER="/var/lib/prometheus/node-exporter/" # DEFAULT UBUNTU LOCATION
TARGET_BIN_PATH="/usr/local/bin"
EXEC_PATH="$(realpath $(dirname $0))"

# STATUS PRETTY PRINT DECLARATION
OK=" [\033[0;32m OK \033[0m]"
KO=" [\033[0;31m KO \033[0m]"
SKIP=" [\033[0;33mSKIP\033[0m]"
WARN=" [\033[0;33mWARN\033[0m]"
RUN=" [\033[0;32m -> \033[0m]"

# CHECK SCRIPT OPTIONS
while getopts ":c:v?" opt; do
  case $opt in
    c)
      TARGET_CONFIG_PATH="$OPTARG" >&2
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

# SET CONFIG LOCATION TO DEFAULT VALUE IF NO ARGUMENT
if [ -z "$TARGET_CONFIG_PATH" ]
then
    TARGET_CONFIG_PATH="$IUSER_HOME/.lotus-exporter-farcaster"
else
    CUSTOM_CONFIG_ARG="-c"
    CUSTOM_CONFIG_PATH="$TARGET_CONFIG_PATH"
fi

# RUN CHECKS
if [ "$(id -u)" -ne 0 ]
then
    echo
	echo -e "$KO must be run as root"
    exit 1
elif [ ! "$(id $IUSER)" ]
then
    echo
	echo -e "$KO user $IUSER doesn't exist"
    exit 1
elif [ -z "$IUSER_HOME" ]
then
    echo
    echo -e "$KO cannot find user $IUSER home"
    exit 1
elif [ ! -f "$IUSER_HOME/.lotusminer/config.toml" ]
then
    echo
	echo "$WARN user $IUSER doesn't seems to be a lotus user $IUSER_HOME/.lotusminer/config.toml doesn't exist"
    echo "Continuing anyway"
fi

verify() {
if [ "$?" -eq 0 ]
then
    echo -e "$OK"
else
    MSG="$1"
    echo -e "$KO" 
    echo "$MSG"
    echo -e "$TRACELOG"
    echo -e "\033[0;31mAborting !!\033[0m"
    exit 1
fi
}

verify_silent_ok() {
if [ "$?" -ne 0 ]
then
    MSG="$1"
    echo -e "$KO" 
    echo "$MSG"
    echo -e "$TRACELOG"
    echo -e "\033[0;31mAborting !!\033[0m"
    exit 1
fi
}


# Install Debian requirements
PKG_LIST="python3-toml python3-aiohttp python3-pip python3-requests-toolbelt prometheus-node-exporter"
while true; do
    read -n 1 -s -p "Install required debian packages ($PKG_LIST) ? " yn
    case $yn in
        [Yy]* ) echo -n "Yes"; TRACELOG=$(apt-get install $PKG_LIST 2>&1); verify "apt-get install $PKG_LIST"; break;;
        [Nn]* ) echo -e "No$SKIP"; break;;
        * ) read -t 0.01 junk; echo -e "\nPlease answer Y or N." ;;
    esac
done

# Verify prometheus-node-exporter work properly
echo -n "Verify local prometheus node exporter connectivity"
TRACELOG=$(curl -vs -o - http://localhost:9100/metrics 2>&1)
verify "curl -vs -o - http://localhost:9100/metrics"

# Configure prometheus node exporter folder
# It seems like sometimes the prometheus-node-exporter remove the rights to the folder. I suspect the folder is not created yet
echo -n "Configure prometheus node exporter folder"
TRACELOG=$(mkdir -p "$PROMETHEUS_NODE_EXPORTER_FOLDER" 2>&1)
verify_silent_ok "mkdir -p \"$PROMETHEUS_NODE_EXPORTER_FOLDER\""
TRACELOG=$(chmod g+r "$PROMETHEUS_NODE_EXPORTER_FOLDER" 2>&1)
verify_silent_ok "chmod g+r \"$PROMETHEUS_NODE_EXPORTER_FOLDER\""
TRACELOG=$(chmod g+w "$PROMETHEUS_NODE_EXPORTER_FOLDER" 2>&1)
verify_silent_ok "chmod g+w \"$PROMETHEUS_NODE_EXPORTER_FOLDER\""
TRACELOG=$(chgrp "$IUSER" "$PROMETHEUS_NODE_EXPORTER_FOLDER" 2>&1)
verify "chgrp \"$IUSER\" \"$PROMETHEUS_NODE_EXPORTER_FOLDER\""

# Install python modules
while true; do
    read -n 1 -s -p "Install python modules ? " yn
    case $yn in
        [Yy]* ) echo -n "Yes"; TRACELOG=$(pip3 install py-multibase gql 2>&1); verify "pip3 install py-multibase gql"; break;;
        [Nn]* ) echo -e "No$SKIP"; break;;
        * ) read -t 0.01 junk; echo -e "\nPlease answer Y or N." ;;
    esac
done

# Install farcaster
while true; do
    read -n 1 -s -p "Install farcaster binary ? " yn
    case $yn in
        [Yy]* )
            echo -n "Yes";
            TRACELOG=$(cp "$EXEC_PATH/lotus-exporter-farcaster.py" "$TARGET_BIN_PATH/" 2>&1) ;
            verify_silent_ok "cp \"$EXEC_PATH/lotus-exporter-farcaster.py\" \"$TARGET_BIN_PATH/\"" ;
            TRACELOG=$(chown "$IUSER" "$TARGET_BIN_PATH/lotus-exporter-farcaster.py" 2>&1) ;
            verify_silent_ok "chown \"$IUSER\" \"$TARGET_BIN_PATH/lotus-exporter-farcaster.py\"" ;
            TRACELOG=$(chmod +x "$TARGET_BIN_PATH/lotus-exporter-farcaster.py" 2>&1) ;
            verify "chmod +x \"$TARGET_BIN_PATH/lotus-exporter-farcaster.py\"" ;

            echo -n "Install cron job"
            if [ -z "$CUSTOM_CONFIG_ARG" ]
            then
                TRACELOG=$(cat "$EXEC_PATH/lotus-exporter-farcaster.cron" |sed "s/LOTUS_USER/$IUSER/;s|TARGET_BIN_PATH|$TARGET_BIN_PATH|; s|CUSTOM_CONFIG_ARG|| ;w /etc/cron.d/lotus-exporter-farcaster" 2>&1)
                verify "cron job creation"
            else
                TRACELOG=$(cat "$EXEC_PATH/lotus-exporter-farcaster.cron" |sed "s/LOTUS_USER/$IUSER/;s|TARGET_BIN_PATH|$TARGET_BIN_PATH|; s|CUSTOM_CONFIG_ARG|$CUSTOM_CONFIG_ARG \"$CUSTOM_CONFIG_PATH\"| ;w /etc/cron.d/lotus-exporter-farcaster" 2>&1)
                verify "cron job creation"
            fi

            echo -n "Configure farcaster"
            TRACELOG=$(mkdir -p "$TARGET_CONFIG_PATH/" 2>&1)
            verify_silent_ok "mkdir -p \"$TARGET_CONFIG_PATH/\""
            TRACELOG=$(cp "$EXEC_PATH/addresses.toml.example" "$TARGET_CONFIG_PATH/" 2>&1)
            verify_silent_ok "cp \"$EXEC_PATH/addresses.toml.example\" \"$TARGET_CONFIG_PATH/\""
            TRACELOG=$(cp "$EXEC_PATH/config.toml.example" "$TARGET_CONFIG_PATH/" 2>&1)
            verify "cp \"$EXEC_PATH/config.toml.example\" \"$TARGET_CONFIG_PATH/\""
            TRACELOG=$(chown "$IUSER" "$TARGET_CONFIG_PATH/" "$TARGET_CONFIG_PATH/addresses.toml.example" "$TARGET_CONFIG_PATH/config.toml.example" 2>&1)
            verify_silent_ok "chown \"$IUSER\" \"$TARGET_CONFIG_PATH/\" \"$TARGET_CONFIG_PATH/addresses.toml.example\" \"$TARGET_CONFIG_PATH/config.toml.example\" "
            break;;
        [Nn]* ) echo -e "No$SKIP"; break;;
        * ) read -t 0.01 junk; echo -e "\nPlease answer Y or N." ;;
    esac
done


# LAUNCH AUTOMATIC ASSISTANT TO CREATE config.toml
while true; do
    read -n 1 -s -p "Launch configuration assistant ? " yn
    case $yn in
        [Yy]* )
            echo -e "Yes$RUN";
            if [ -z "$CUSTOM_CONFIG_ARG" ]
            then
                # Heavily tricky ! to ensure the full environment is loaded (included lotus variable) we need to :
                # The first -i belongs to sudo. It allows to spawn a new shell (default lotus user shell) and source the basic environment variables (at that point lotus variables are not loaded because .basrh includes a protection at the beginning to prevent .bashrc execution if the shell is not interactive (case $- in; *i*) ;; *) return;;)
                # Then this shell will spawn a subshell based on "$SHELL" variable of the lotus use renvironment. 
                # This subshell is executed with :
                #   -i (so it will be interactive and load the full .bashrc and all the variables including lotus variables !) 
                #   -c to run the assistant script as a command. If we forgot the -c the assistant will be run against the $SHELL shell instead of bash. It might fail if bash is not the default shell
                sudo -u "$IUSER" -i '$SHELL' -i -c "$EXEC_PATH/assistant.sh"
            else
                sudo -u "$IUSER" -i '$SHELL' -i -c "'$EXEC_PATH/assistant.sh' $CUSTOM_CONFIG_ARG '$CUSTOM_CONFIG_PATH'"
            fi
            break;;

        [Nn]* ) echo -e "No$SKIP"; break;;
        * ) read -t 0.01 junk; echo -e "\nPlease answer Y or N." ;;
    esac
done

# LAUNCH CHECK
echo -e "The script is now checking that everything is working fine $RUN" 
if [ -z "$CUSTOM_CONFIG_ARG" ]
then
    $EXEC_PATH/check.sh "$IUSER"
else
    $EXEC_PATH/check.sh "$CUSTOM_CONFIG_ARG" "$CUSTOM_CONFIG_PATH" "$IUSER"
fi


if [ "$?" -ne 0 ]
then
    echo "Aborting!!!"
    exit 1
fi

cat <<EOF
The configuration has been saved here : $TARGET_CONFIG_PATH/config.toml
********************************************************************************

NEXT STEPS : 
- Add this node to your prometheus server
- Add the farecaster dashboard to grafana (import through ui)
- (Optional) Add knwown addresses and external wallets to $TARGET_CONFIG_PATH

********************************************************************************
EOF
exit 0
