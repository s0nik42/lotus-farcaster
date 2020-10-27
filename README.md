# lotus-exporter-farcaster 
Export useful [Lotus](https://github.com/filecoin-project/lotus) node information to [Prometheus](https://prometheus.io/). 
It comes with a [Grafana](https://grafana.com/) dashboard.

# How it works
lotus-exporter-farcaster is a standalone and configuration less python script. That is executed every min via the contab.
It generates metrics that are exposed by node-exporter to prometheus.

# Benefits
* Easy to deploy
* Configuration less
* Small footprint
* Collect lotus node and miner data
* Only rely on API
* Data are pulled from the Prometheus (increase security)  
* Deploy on the miner node only


# Requirements


# Instalation


# Tested environments


# Thanks to

prometheus exporter for Filecoin lotus node
# This script is a node exporter scrapper for lotus (filecoin)
# Default configuration 
#   - miner and deamon token file to be located in ~/.lotus & ~/.lotusminer.
#   - miner and daemon run localy
#   ==> This can be configured using the following variables
