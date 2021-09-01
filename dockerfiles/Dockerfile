FROM python:3.9

# Allow environment variables to be passed as build time arguments
ARG FREQUENCY=50

# Set environment variables to build arguments
ENV FREQUENCY=$FREQUENCY

# Copy lotus-farcaster program and shell script that invokes it to the container
COPY lotus-exporter-farcaster/lotus-exporter-farcaster.py /usr/local/bin/
COPY dockerfiles/docker_run_script.sh /usr/local/bin/

# Create /data which will hold the output of the lotus-farcaster
RUN mkdir /data

# Allow scripts to be run
RUN chmod 0775 /usr/local/bin/lotus-exporter-farcaster.py
RUN chmod 0775 /usr/local/bin/docker_run_script.sh

# Make a link from python3.9 to python3
RUN ln -sv /usr/local/bin/python3.9 /usr/bin/python3

# Add the lib of python
RUN python3 -m pip install aiohttp toml py-multibase

# Run the container on an unprivileged user XXX not implemented yet // need rights to store files to prometheus folder
#RUN useradd -r -u 424242 -U farcaster
#USER farcaster


CMD ["/usr/local/bin/docker_run_script.sh"]
