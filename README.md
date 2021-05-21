![SCREENSHOT](https://github.com/s0nik42/lotus-farcaster/raw/main/images/screenshots/screenshot001.png)

# lotus-farcaster 
is a Visualization and Analytics tool for [Lotus](https://github.com/filecoin-project/lotus) Filecoin node. It provides advance analytics features (Like average sealing time, historical). Its designed to replace your terminal monitoring. Farcaster is developped in cooperation with Protocol Labs. 
It leverages [Prometheus](https://prometheus.io/), [Grafana](https://grafana.com/) and Python.

## Contribution
* Donation Filcoin Address : f3v3lj5jrsvv3nwmsvvj57yyty6ndb27oyi4yaqhwzst3emdv25hefna6vxhtpjb5pytwahdod67syxjyzba3q
* This is an individual open source project, not backed by any companies. If you like it please consider contributing by reaching me out or donate. 

Thank you !

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
|Fil+         | OK          | Visualize granted datacap|
|Adress lookup| OK          | View names instead of boring adresses |
|Deals        | Partial     | Sealing Deals     |

## Requirements
* A Grafana/Prometheus working environment (local or remote)
  * [Grafana installation guide](https://grafana.com/docs/grafana/latest/installation/debian/)  (Version 7.4.0)
  * Prometheus is available as package in ubuntu 20.04 (Version 2.20.1)

* Locally installed on the miner node only:
  * prometheus-node-exporter
  * python3-toml
  * python3-aiohttp
  * py-multibase
  * lotus-exporter-farcaster

## Install lotus-exporter-farcaster (Ubuntu)
```
git clone https://github.com/s0nik42/lotus-farcaster.git
cd lotus-farcaster/lotus-exporter-farcaster
chmod +x install.sh
./install.sh LOTUS_USER_USERNAME
```

## Install the Grafana Dashboard 
Import in Grafana the relevent dashboard file from ./lotus-farcaster/grafana-dashboard

## Tested environments
* Grafana : 7.4.0
* Prometheus : 2.20.1
* Ubuntu : 20.04.1 LT
* Python : 3.8

## Docker

Farcaster can also run as a Docker container. The container that corresponds to this
repository will run the `docker_run_script.sh` script which just loops
over calling lotus-farcaster code at a specific frequency (default: every minute)
This can be overriden by editing the Dockerfile. In case execution exceed the set requency,
the execution restart after 10 seconds.
The output of the lotus-farcaster is written to `/data/farcaster.prom`
inside the container which should be a bind mount in prometheus node exporter path.

Optional : This could be use in conjunction with a dockerised version of prometheus 
node_exporter ([instructions](https://github.com/prometheus/node_exporter) to get the
node_exporter container going

### Building the container (as root)
```
apt install docker.io
docker build -t lotus-farcaster:latest -f dockerfiles/Dockerfile .
```

### Running the container (as root)
Set the 3 variables below (LOTUS_PATH, LOTUS_MINER_PATH, PROMETHEUS_NODE_EXPORTER_PATH),
accordingly to your setup and simply copy paste the run command below.

```
export LOTUS_PATH="/opt/lotus/.lotus/"
export LOTUS_MINER_PATH="/opt/lotus/.lotusminer/"
export LOTUS_FARCASTER_PATH="/opt/lotus/.lotus-exporter-farcaster/"
export PROMETHEUS_NODE_EXPORTER_PATH="/var/lib/prometheus/node-exporter/"

docker run --name lotus-farcaster -d \
  --mount type=bind,source=$LOTUS_PATH,target=/root/.lotus,readonly \
  --mount type=bind,source=$LOTUS_MINER_PATH,target=/root/.lotusminer,readonly \
  --mount type=bind,source=$LOTUS_FARCASTER_PATH,target=/root/.lotus-exporter-farcaster,readonly \
  --mount type=bind,source=$PROMETHEUS_NODE_EXPORTER_PATH,target=/data \
  --network=host \
  lotus-farcaster
```

### Docker Debug (as root)
```
docker ps [-a]
docker logs lotus-farcaster
docker exec -it lotus-farcaster bash 
```

### Uninstall docker (as root)
```
docker stop lotus-farcaster
docker rm lotus-farcaster
docker image rm lotus-farcaster
```

## Contact
* Slack : @Julien_NOEL_-_Twin_Quasar_(s0nik42) 

## Sponsors
[<img src="https://github.com/s0nik42/lotus-farcaster/raw/main/images/sponsors/protocol-labs.png" alt="Protcol Labs" width="250">
](https://protocol.ai/)

