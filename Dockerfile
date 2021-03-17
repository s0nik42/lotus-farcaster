FROM python:3.9

# Allow environment variables to be passed as build time arguments
ARG MINER_URL="http://127.0.0.1:2345/rpc/v0"
ARG MINER_TOKEN
ARG MINER_TOKEN_FILE
ARG DAEMON_URL="http://127.0.0.1:1234/rpc/v0"
ARG DAEMON_TOKEN
ARG DAEMON_TOKEN_FILE
ARG SLEEP=10

# Set environment variables to build arguments
ENV MINER_URL=$MINER_URL
ENV MINER_TOKEN=$MINER_TOKEN
ENV MINER_TOKEN_FILE=$MINER_TOKEN_FILE
ENV DAEMON_URL=$DAEMON_URL
ENV DAEMON_TOKEN=$DAEMON_TOKEN
ENV DAEMON_TOKEN_FILE=$DAEMON_TOKEN_FILE
ENV SLEEP=$SLEEP

# Copy lotus-farcaster program and shell script that invokes it to the container
COPY lotus-exporter-farcaster/lotus-exporter-farcaster.py /usr/local/bin/
COPY docker_run_script.sh /usr/local/bin/farcaster

# Create /data which will hold the output of the lotus-farcaster
RUN mkdir /data

# Allow scripts to be run
RUN chmod 0775 /usr/local/bin/lotus-exporter-farcaster.py
RUN chmod 0775 /usr/local/bin/farcaster

CMD ["/usr/local/bin/farcaster"]
