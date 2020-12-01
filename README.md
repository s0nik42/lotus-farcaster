![SCREENSHOT](https://github.com/s0nik42/lotus-farcaster/raw/main/images/screenshots/screenshot001.png)


# lotus-farcaster 
is a Visualization and Analytics tool for [Lotus](https://github.com/filecoin-project/lotus) Filecoin node. Developped in cooperation with Protocol Labs. 
It leverages [Prometheus](https://prometheus.io/), [Grafana](https://grafana.com/) and Python.

## Contribution
* Donation Filcoin Address : f3v3lj5jrsvv3nwmsvvj57yyty6ndb27oyi4yaqhwzst3emdv25hefna6vxhtpjb5pytwahdod67syxjyzba3q
* This is an individual open source project, not backed by any companies. If you like it please consider contributing by reaching me out or donate. 

Thank you !

## Version 

This is a BETA PUBLIC VERSION. It cannot break your lotus installation, but you may face bugs or inaccurate information. Please consider giving feedbacks by opening issues.

## How it works
lotus farcaster comes with 2 Components :
* A Grafana dashboard
* lotus-exporter-farcaster a standalone and configuration-less python script executed every minute by the crontab.
It generates metrics that are exposed by node-exporter to prometheus.

## Benefits
* Easy to deploy
* Configuration less
* Small footprint
* Collect lotus node and miner data
* Only rely on API
* Data are pulled from the Prometheus (increase security)  
* Deploy on the miner node only
* Run under Unprivileged user

## Dashboard Features
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
|Deadlines    | OK          |                   |
|Deals        | Partial     |                   |
|Gas Price    | Comming Soon|                   |
|Won Blocks   | Roadmap     |                   |

## Requirements
* A Grafana/Prometheus working environment (local or remote)
  * [Grafana installation guide](https://grafana.com/docs/grafana/latest/installation/debian/)  (Version 7.3.1)
  * Prometheus is available as package in ubuntu 20.04 (Version 2.20.1)

* Locally installed on the miner node only:
  * prometheus-node-exporter
  * python3-toml
  * lotus-exporter-farcaster

## Instalation of lotus-exporter-farcaster (Ubuntu)
```
git clone https://github.com/s0nik42/lotus-farcaster.git
cd lotus-farcaster/lotus-exporter-farcaster
chmox +x install.sh
./install.sh LOTUS_USERNAME
```

## Instalation of the Grafana Dashboard 
Import in Grafana the relevent dashboard file from ./lotus-farcaster/grafana-dashboard

## Tested environments
* Grafana : 7.3.1
* Prometheus : 2.20.1
* Ubuntu : 20.04.1 LT
* Python : 3.8

## Contact
* Slack : @s0nik42

## Sponsors
![name](<img src="https://github.com/s0nik42/lotus-farcaster/raw/main/images/sponsors/protocol-labs.png" alt="Protcol Labs" width="250">](http://google.com)
<img src="https://github.com/s0nik42/lotus-farcaster/raw/main/images/sponsors/protocol-labs.png" alt="Protcol Labs" width="250">
