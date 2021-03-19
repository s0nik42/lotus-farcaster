#!/bin/sh -e

while true; do
  /usr/local/bin/lotus-exporter-farcaster.py > /data/lotus-farcaster.prom
  sleep $SLEEP
done
