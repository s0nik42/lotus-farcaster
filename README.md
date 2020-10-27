# lotus-farcaster 
is a Visualization and Analytics tool for [Lotus](https://github.com/filecoin-project/lotus) Filecoin node
It leverages [Prometheus](https://prometheus.io/), [Grafana](https://grafana.com/) and Python.

# How it works
lotus farcaster comes with 2 Components :
* A Grafana dashboard
* lotus-exporter-farcaster a standalone and configuration-less python script executed every minute by the crontab.
It generates metrics that are exposed by node-exporter to prometheus.

# Benefits
* Easy to deploy
* Configuration less
* Small footprint
* Collect lotus node and miner data
* Only rely on API
* Data are pulled from the Prometheus (increase security)  
* Deploy on the miner node only
* Run under Unprivileged user

# Dashboard Features
|Feature      |Status       |Comments           |
|-------------|-------------|-------------------|
|Sectors      | OK          |                   |
|Mpool        | OK          |                   |
|Storage Info | OK          |                   |
|Workers Info | OK          |                   |
|Sealing      | OK          |Job + Scheduler    |
|Power        | OK          |                   |
|Wallets      | OK          |                   |
|Chain        | OK          |Head + Sync Status |
|Deals        | OK          |                   |
|Deadlines    | Comming Soon|                   |
|Gas Price    | Comming Soon|                   |
|Won Blocks   | Roadmap     |                   |

# Requirements
* A Grafana/Prometheus working environment (local or remote)
* Locally installed on the miner :
  * prometheus-node-exporter
  * lotus-exporter-farcaster

# Instalation (Ubuntu)
```
cd /usr/src
git clone https://github.com/s0nik42/lotus-farcaster.git
cp lotus-farcaster/lotus-exporter-farcaster/lotus-exporter-farcaster.py /usr/local/bin
```
# First execution (assuming usernmane is "lotus")
If the script is executed with the same user than lotus miner and lotus node. its configuration less.
If you execute the sript with another user. A few set of variables are available editing at the beginning of the script.
## Testing the script is working fine, the following command should return all the metrics and end up nicely
```
sudo -u lotus /usr/local/bin/lotus-exporter-farcaster.py
```
## Testing the prometheus-node-exporter integration
We're assuming here you already have a working prometheus-node-exporter
* The following line is exporting the metrics to the local prometheus-node-exporter. It should end up nicely and you should look at the they is no error coming from rometheus-node-exporter.
```
sudo -u lotus 'if lotus-farcaster/lotus-exporter-farcaster/lotus-exporter-farcaster.py > /var/lib/prometheus/node-exporter/lotus_get.prom.$$;  then mv /var/lib/prometheus/node-exporter/farcaster.prom.$$ /var/lib/prometheus/node-exporter/farcaster.prom; else rm /var/lib/prometheus/node-exporter/farcaster.prom.$$; fi'
tail -n 100 -f /var/log/syslog
```
* Finally you can connect to the local prometheus-node-exporter and find lotus metrics (search for lotus_daemon_info) : http://HOSTNAME:9100/metrics


# Tested environments
* Grafana : 7.1.5
* Prometheus : 2.20.1
* Ubuntu : 20.04.1 LT
* Python : 3.8

