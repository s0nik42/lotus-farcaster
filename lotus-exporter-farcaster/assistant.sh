#!/bin/bash
#@author: s0nik42
#Copyright (c) 2021 Julien NOEL (s0nik42)
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

# CONNEXION VARIABLES THIS SCRIPT IS PRODUCING
miner_api=""
daemon_api=""
markets_api=""

help_message () {
      echo "Usage : $(basename $0) [ -c folder ]
    Autodetect lotus configuration and generate lotus-exporter-farcaster
    configuration file

    This script scan environment for well knowned variables and paths
    and try to generate lotus-exporter-farcaster config file : config.toml

    IMPORTANT : This script must be ran after lotus-exporter-frcaster
    installation on the same server as the lotus-miner

    This script must be run under the same user owning the lotus-miner
    process on the server

    Options:
      -c folder   specify the target configutation file location for 
                  lotus-exporter-farcaster. This option is useful in case 
                  multiple miners run on the same server. 
                  Default : ~/.lotus-exporter-farcaster
                  "
}


# INTERNAL VARIABLES
EXEC_PATH="$(realpath $(dirname $0))"

# STATUS PRETTY PRINT DECLARATION
OK=" [\033[0;32m OK \033[0m]"
KO=" [\033[0;31m KO \033[0m]"
SKIP=" [\033[0;33mSKIP\033[0m]"
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

# SET CONFIG LOCATION TO DEFAULT VALUE IF NO ARGUMENT
if [ -z "$TARGET_CONFIG_PATH" ]
then
    TARGET_CONFIG_PATH="$HOME/.lotus-exporter-farcaster"
fi

################################################################################
# SEARCH FOR LOTUS MINER
################################################################################
echo -e "   Configure Miner API connection string $RUN"


display () {
echo $1|sed "s/^\(.....\)[^:]*\(.....:\)/\1...\2/"
}

# IF API VARIABLE SET
if [ -n "$MINER_API_INFO" ]
then
    while true; do
        read -n 1 -s -p "       Use info from \$MINER_API_INFO [$(display $MINER_API_INFO)] ? " yn
        case $yn in
            [Yy]* ) echo -e "Yes$OK" ; miner_api="$MINER_API_INFO"; break;;
            [Nn]* ) echo -e "No$SKIP"; break;;
            * ) read -t 0.01 junk; echo -e "\n       Please answer Y or N." ;;
        esac
    done
fi

# IF PATH VARIABLE SET AND BOTH TOKEN AND API are available
if [ -z "$miner_api" -a -n  "$LOTUS_MINER_PATH" ]
then
    miner_api_token=$(cat "$LOTUS_MINER_PATH/token" 2>/dev/null)
    miner_api_url=$(cat "$LOTUS_MINER_PATH/api" 2>/dev/null)

    if [ -n "$miner_api_token" -a -n "$miner_api_url" ]
    then
        while true; do
            read -n 1 -s -p "       Use info found in \$LOTUS_MINER_PATH  [$(display $miner_api_token:$miner_api_url)] ? " yn
            case $yn in
                [Yy]* ) echo -e "Yes$OK" ; miner_api="$miner_api_token:$miner_api_url"; break;;
                [Nn]* ) echo -e "No$SKIP"; break;;
                * ) read -t 0.01 junk; echo -e "\n       Please answer Y or N." ;;
            esac
        done
    fi
fi

# CHECK CONTENT OF ~/.lotusminer if the value is different from LOTUS_MINER_PATH variable
if [ -z "$miner_api" -a  "$(realpath "$LOTUS_MINER_PATH" 2>/dev/null)" != "$(realpath "$HOME/.lotusminer" 2>/dev/null)" ]
then
    miner_api_token=$(cat "$HOME/.lotusminer/token" 2>/dev/null)
    miner_api_url=$(cat "$HOME/.lotusminer/api" 2>/dev/null)

    if [ -n "$miner_api_token" -a -n "$miner_api_url" ]
    then
        while true; do
            read -n 1 -s -p "       Use info found in ~/.lotusminer path [$(display $miner_api_token:$miner_api_url)] ? " yn
            case $yn in
                [Yy]* ) echo -e "Yes$OK" ; miner_api="$miner_api_token:$miner_api_url"; break;;
                [Nn]* ) echo -e "No$SKIP"; break;;
                * ) read -t 0.01 junk; echo -e "\n       Please answer Y or N." ;;
            esac
        done
    fi

fi

if [ -z "$miner_api" ]
then
        while true; do
            read -e -p "       No connection string autodetected, set it manually (format : <TOKEN>:ip4/<IP_ADDRESS>/tcp/<PORT>/http) : " miner_api
            case $miner_api in
                "" ) ;;
                * ) break;;
            esac
        done
fi

################################################################################
# SEARCH FOR LOTUS DAEMON
################################################################################
echo -e "   Configure Daemon API connection string $RUN"

# IF API VARIABLE SET
if [ -n "$FULLNODE_API_INFO" ]
then
    while true; do
        read -n 1 -s -p "       Use info found in FULLNODE_API_INFO variable [$(display $FULLNODE_API_INFO)] ? " yn
        case $yn in
            [Yy]* ) echo -e "Yes$OK" ; daemon_api="$FULLNODE_API_INFO"; break;;
            [Nn]* ) echo -e "No$SKIP"; break;;
            * ) read -t 0.01 junk; echo -e "\n       Please answer Y or N." ;;
        esac
    done
fi

# IF PATH VARIABLE SET AND BOTH TOKEN AND API are available
if [ -z "$daemon_api" -a -n  "$LOTUS_PATH" ]
then
    daemon_api_token=$(cat "$LOTUS_PATH/token" 2>/dev/null)
    daemon_api_url=$(cat "$LOTUS_PATH/api" 2>/dev/null)

    if [ -n "$daemon_api_token" -a -n "$daemon_api_url" ]
    then
        while true; do
            read -n 1 -s -p "       Use info found in LOTUS_PATH variable [$(display $daemon_api_token:$daemon_api_url)] ? " yn
            case $yn in
                [Yy]* ) echo -e "Yes$OK" ; daemon_api="$daemon_api_token:$daemon_api_url"; break;;
                [Nn]* ) echo -e "No$SKIP"; break;;
                * ) read -t 0.01 junk; echo -e "\n       Please answer Y or N." ;;
            esac
        done
    fi
fi

# CHECK CONTENT OF ~/.lotus if the value is different from LOTUS_PATH variable
if [ -z "$daemon_api" -a  "$(realpath "$LOTUS_PATH" 2>/dev/null)" != "$(realpath "$HOME/.lotus" 2>/dev/null)" ]
then
    daemon_api_token=$(cat "$HOME/.lotus/token" 2>/dev/null)
    daemon_api_url=$(cat "$HOME/.lotus/api" 2>/dev/null)

    if [ -n "$daemon_api_token" -a -n "$daemon_api_url" ]
    then
        while true; do
            read -n 1 -s -p "       Use info found in ~/.lotus path [$(display $daemon_api_token:$daemon_api_url)] ? " yn
            case $yn in
                [Yy]* ) echo -e "Yes$OK" ; daemon_api="$daemon_api_token:$daemon_api_url"; break;;
                [Nn]* ) echo -e "No$SKIP"; break;;
                * ) read -t 0.01 junk; echo -e "\n       Please answer Y or N." ;;
            esac
        done
    fi

fi

if [ -z "$daemon_api" ]
then
        while true; do
            read -e -p "       No connection string autodetected, set it manually (format : <TOKEN>:ip4/<IP_ADDRESS>/tcp/<PORT>/http) : " daemon_api
            case $daemon_api in
                "" ) ;;
                * ) break;;
            esac
        done
fi

################################################################################
# SEARCH FOR LOTUS MARKETS
################################################################################


# VERIFY ABOUT MARKETS NODE
while true; do
    read -n 1 -s -p "   Does the miner has a markets node (if unsure answer no) ? " yn
    case $yn in
        [Yy]* ) echo -e "Yes$OK" ; break;;
        [Nn]* ) echo -e "No$SKIP"; markets_api="$miner_api"; break;;
        * ) read -t 0.01 junk; echo -e "\n   Please answer Y or N." ;;
    esac
done

if [ -z "$markets_api" ]
then
    echo -e "   Configure Markets API connection string $RUN"

    # IF API VARIABLE SET
    if [ -n "$MARKETS_API_INFO" ]
    then
        while true; do
            read -n 1 -s -p "       Use info found in MARKETS_API_INFO variable [$(display $MARKETS_API_INFO)] ? " yn
            case $yn in
                [Yy]* ) echo -e "Yes$OK" ; markets_api="$MARKETS_API_INFO"; break;;
                [Nn]* ) echo -e "No$SKIP"; break;;
                * ) read -t 0.01 junk; echo -e "\n       Please answer Y or N." ;;
            esac
        done
    fi
fi

# IF PATH VARIABLE SET AND BOTH TOKEN AND API are available
if [ -z "$markets_api" -a -n  "$LOTUS_MARKETS_PATH" ]
then
    markets_api_token=$(cat "$LOTUS_MARKETS_PATH/token" 2>/dev/null)
    markets_api_url=$(cat "$LOTUS_MARKETS_PATH/api" 2>/dev/null)

    if [ -n "$markets_api_token" -a -n "$markets_api_url" ]
    then
        while true; do
            read -n 1 -s -p "       Use info found in LOTUS_MARKETS_PATH variable [$(display $markets_api_token:$markets_api_url)] ? " yn
            case $yn in
                [Yy]* ) echo -e "Yes$OK" ; markets_api="$markets_api_token:$markets_api_url"; break;;
                [Nn]* ) echo -e "No$SKIP"; break;;
                * ) read -t 0.01 junk; echo -e "\n       Please answer Y or N." ;;
            esac
        done
    fi
fi

# CHECK CONTENT OF ~/.lotusmarkets if the value is different from LOTUS_MARKETS_PATH variable
if [ -z "$markets_api" -a  "$(realpath "$LOTUS_MARKETS_PATH" 2>/dev/null)" != "$(realpath "$HOME/.lotusmarkets" 2>/dev/null)" ]
then
    markets_api_token=$(cat "$HOME/.lotusmarkets/token" 2>/dev/null)
    markets_api_url=$(cat "$HOME/.lotusmarkets/api" 2>/dev/null)

    if [ -n "$markets_api_token" -a -n "$markets_api_url" ]
    then
        while true; do
            read -n 1 -s -p "       Use info found in ~/.lotusmarkets path [$(display $markets_api_token:$markets_api_url)] ? " yn
            case $yn in
                [Yy]* ) echo -e "Yes$OK" ; markets_api="$markets_api_token:$markets_api_url"; break;;
                [Nn]* ) echo -e "No$SKIP"; break;;
                * ) read -t 0.01 junk; echo -e "\n       Please answer Y or N." ;;
            esac
        done
    fi

fi

if [ -z "$markets_api" ]
then
        while true; do
            read -e -p "       No connection string autodetected, set it manually (format : <TOKEN>:ip4/<IP_ADDRESS>/tcp/<PORT>/http) : " markets_api
            case $markets_api in
                "" ) ;;
                * ) break;;
            esac
        done
fi


# SAVE FILE
sed "s|<MINER_API_STRING>|$miner_api| ; s|<MARKETS_API_STRING>|$markets_api| ;s|<DAEMON_API_STRING>|$daemon_api|" > "$TARGET_CONFIG_PATH/config.toml" < "$EXEC_PATH/config.toml.example"
exit
