This Farcaster add-on enhances metrics by associating sectors with physical equipment, facilitating real-time calculation of sector-specific power consumption.

This is related to the Filecoin green initiative project: https://github.com/twinquasar/green

## Deployment

1. Install and confgure lotus-exporter-farcaster
2. Install lotus-exporter-farcaster-green

```bash
cp lotus-exporter-farcaster-green.py /usr/local/bin/
```

3. Configuration

both lotus-exporter-farcaster and lotus-exporter-farcaster-green share the same configuration file
Add the folowing sections to lotus-exporter-farcaster configuration file

```yaml
[green]
# The list of all infra equipment shared by this miner, there consumption will be equaly shared accross all Filecoin equipment
global_infra_equipment = [ "switch-01", "switch-02", "fw-01", "fw-02"]

[green.worker_equipments]
# miner is amandatory entry linking the miner alias to the real miner server name. This is also where this script should run
miner = "miner-01"
# List the mapping of the filecoin workers process name and the name of the physical equipment running them. This is usefull especially when you have multiple workers running on the same physical server
PC2-w01 = "worker-1"
C2-w02 = "worker-1"
PC1-w01 = "worker-3"
RU2-w01 = "worker-4"

[green.storage_equipments]
# List all the storage location when running on external equipment like jbods
0553534f-b78b-44f5-a2d4-c630d84364b3="data60-1"
f543TREE-7694-4d21-8147-f36f64aa8aac="data60-1"
bd456767-dd22-4e83-8768-c6d55470274d="worker-1"
0546560f-a9e4-4643-acc3-a32aa6c995a2="worker-1"
2ca74324-434'-46bd-907f-3af345344358="worker-3"
e161432d-b8c0-45c4-ba8d-d4f433243243="worker-4"
1443244c-02bb-46d3-b502-5c4332442346="miner-01"
```

4. Add to cron 

```bash
echo '* * * * *   lotus if /usr/local/bin/lotus-exporter-farcaster-green.py  > /var/lib/prometheus/node-exporter/farcaster-green.prom.$$;  then mv /var/lib/prometheus/node-exporter/farcaster-green.prom.$$ /var/lib/prometheus/node-exporter/farcaster-green.prom; else rm /var/lib/prometheus/node-exporter/farcaster-green.prom.$$; fi' >> /etc/cron.d/lotus-exporter-farcaster
```
