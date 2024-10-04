#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=C0301, W0511, W0603, W0703, R0914, R0912, R0915, R0902, R0201, C0302, C0103, W1202
"""
@author: s0nik42
Copyright (c) 2023 Twin Quasar

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# Release v1
# Filecoingreen

from urllib.parse import urlparse
from pathlib import Path
import json
import time
import sys
import socket
import os
import asyncio
import argparse
import logging
from functools import wraps
import toml
import aiohttp

VERSION = "v1.0"

#################################################################################
# CLASS DEFINITION
#################################################################################

class Error(Exception):
    """Exception from this module"""

    @classmethod
    def wrap(cls, f):
        """wrap function to manage exception as a decorator"""
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except cls:
                # Don't wrap already wrapped exceptions
                raise
            except Exception as exc:
                raise exc
        return wrapper

class MinerError(Error):
    """Customer Exception to identify error coming from the miner. Used  for the dashboard Status panel"""

class Lotus():
    """Lotus class is a common parent class to Miner and Daemon Class"""
    target = "lotus"
    Error = Error

    def __init__(self, url, token):
        self.url = url
        self.token = token

    @Error.wrap
    def get(self, method, params):
        """Send a request to the daemon API / This function rely on the function that support async, but present a much simpler interface"""
        result = self.get_multiple([[method, params]])[0]

        if result is None:
            raise MinerError(f"API returned nothing could be an incorrect API key\nTarget : {self.target}\nMethod : {method}\nParams : {params}\nResult : {result}")
        elif "error" in result.keys():
            raise Error(f"\nTarget : {self.target}\nMethod : {method}\nParams : {params}\nResult : {result}")
        return result

    @Error.wrap
    def get_multiple(self, requests):
        """ Send multiple request in Async mode to the daemon API"""
        return asyncio.run(self.__get_json_multiple(self.url, self.token, requests))

    @classmethod
    async def __get_json_multiple(cls, url, token, requests):
        async with aiohttp.ClientSession() as session:
            tasks = []
            for request in requests:
                tasks.append(asyncio.ensure_future(cls.__get_json(session, url, token, request)))
            return await asyncio.gather(*tasks)

    @staticmethod
    async def __get_json(session, url, token, request):
        header = {'Authorization': 'Bearer ' + token}
        method = request[0]
        params = request[1]
        jsondata = {"jsonrpc": "2.0", "method": "Filecoin." + method, "params": params, "id": 3}

        async with session.post(url, json=jsondata, headers=header) as response:
            return await response.json(content_type=None)

class Miner(Lotus):
    """ Miner class"""
    target = "miner"
    Error = MinerError
    miner_id = None

    @Error.wrap
    def id(self):
        """ return miner ID"""
        if self.miner_id is None:
            actoraddress = self.get("ActorAddress", [])
            self.miner_id = actoraddress['result']
        return self.miner_id

    @Error.wrap
    def get_storagelist_enhanced(self):
        """ Get storage list enhanced with reverse hostname lookup"""

        storage_list = self.get("StorageList", [])

        storage_local_list = self.get("StorageLocal", [])
        res = []
        for storage in storage_list["result"].keys():
            storage_info = self.get("StorageInfo", [storage])

            sto = {}
            if storage in storage_local_list["result"].keys():
                sto["path"] = storage_local_list["result"][storage]
            else:
                sto["path"] = ''

            sto["storage_id"] = storage_info["result"]["ID"]
            sto["url"] = storage_info["result"]["URLs"][0]
            sto["host_ip"] = urlparse(sto["url"]).hostname
            try:
                sto["host_name"] = socket.gethostbyaddr(sto["host_ip"])[0]
            except Exception:
                sto["host_name"] = sto["host_ip"]

            sto["host_port"] = urlparse(sto["url"]).port
            sto["weight"] = storage_info["result"]["Weight"]
            sto["can_seal"] = storage_info["result"]["CanSeal"]
            sto["can_store"] = storage_info["result"]["CanStore"]
            try:
                storage_stat = self.get("StorageStat", [storage])
            except Exception:
                sto["capacity"] = 0
                sto["available"] = 0
                sto["reserved"] = 0
            else:
                sto["capacity"] = storage_stat["result"]["Capacity"]
                sto["available"] = storage_stat["result"]["Available"]
                sto["reserved"] = storage_stat["result"]["Reserved"]
            res.append(sto)
        return res

class Metrics():
    """ This class manage prometheus metrics formatting / checking / print """

    # Prefix to all metrics generated by this script
    __PREFIX = "lotus_green_"

    # Full inventory of all metrics allowed with description  and type
    __METRICS_LIST = {
        "scrape_duration_seconds"                   : {"type" : "gauge", "help": "execution time of the different collectors"},
        "scrape_execution_succeed"                  : {"type" : "gauge", "help": "return 1 if lotus-farcaster-green execution was successfully"},
        "sector_resource"                     : {"type" : "gauge", "help": "resource consummed by the sector"}
    }

    __metrics = []

    def __init__(self, output=sys.stdout):
        self.__start_time = time.time()
        self.__last_collector_start_time = self.__start_time
        self._output = output

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *args):
        self.add("scrape_duration_seconds", value=(time.time() - self.__start_time), collector="All")

        # GENERATE EXIT CODE AND PRINT OUTPUT
        if exc_type is None:
            success = 1
        else:
            if exc_type == MinerError:
                success = -2
            elif exc_type is not None:
                success = 0

            # Clear the existing metrics list
            self.__metrics = []

        self.add("scrape_execution_succeed", value=success)
        self.print_all()

    def add(self, metric: str = "", value: float = 1, **labels):
        """ add a new metrics """

        # Check if metric is in the list of the metrics allowed
        if metric in self.__METRICS_LIST.keys():
            self.__metrics.append({"name": metric, "labels": labels, "value": value})
        else:
            raise Exception(f'metric "{metric}" undefined in __METRICS_LIST')

    def print_all(self):
        """ printout all the metrics """

        prev = {}
        # go through all metrics in alphabetic order
        for metric in sorted(self.__metrics, key=lambda m: m['name']):
            m_name = metric["name"]

            # Check if a the HELP and TYPE has already been displayed written
            if prev == {} or m_name is not prev["name"]:
                print(f'# HELP {self.__PREFIX}{ m_name } { self.__METRICS_LIST[m_name]["help"] }', file=self._output)
                print(f'# TYPE {self.__PREFIX}{ m_name } { self.__METRICS_LIST[m_name]["type"] }', file=self._output)

            # Printout the formatted metric
            print(f'{self.__PREFIX}{ m_name } {{ ', end="", file=self._output)
            first = True
            for i in metric["labels"].keys():
                if first is True:
                    first = False
                else:
                    print(', ', end="", file=self._output)
                print(f'{ i }="{ metric["labels"][i] }"', end="", file=self._output)
            print(f' }} { metric["value"] }', file=self._output)
            prev = metric

    def checkpoint(self, collector_name):
        """Measure time for each category of calls to api and generate metrics"""
        now = time.time()
        self.add("scrape_duration_seconds", value=(now - self.__last_collector_start_time), collector=collector_name)
        self.__last_collector_start_time = now

#################################################################################
# FUNCTIONS
#################################################################################
def printj(parsed):
    """JSON PRETTY PRINT // Dev only"""
    print(json.dumps(parsed, indent=4, sort_keys=True))

def load_toml(toml_file):
    """ Load a tmol file into nested dict"""

    # Check if file exists
    if not os.path.exists(toml_file):
        return {}

    # Load file
    try:
        with open(toml_file) as data_file:
            nested_dict = toml.load(data_file)
    except Exception as exp:
        logging.error(f"failed to load file {toml_file}: {exp}")
        raise
    else:
        return nested_dict

def collect(miner, metrics, addresses_config, green):
    """ run metrics collection and export """

    # miner_id
    miner_id = miner.id()

    # GENERATE WORKER INFOS
    workerstats = miner.get("WorkerStats", [])

    # GENERATE JOB INFOS
    workerjobs = miner.get("WorkerJobs", [])
    for (wrk, job_list) in workerjobs["result"].items():
        for job in job_list:
            # job_id = job['ID']['ID']
            sector = str(job['Sector']['Number'])

            try:
                worker_host = workerstats["result"][wrk]["Info"]["Hostname"]
            except Exception:
                # sometime WorkerJobs return invalid worker_id like 0000-000000-0000... in that case return unknown
                worker_host = "unknown"

            try:
                equipment=green["worker_equipments"][worker_host]
            except Exception:
                print(f'Error: {worker_host} not defined in config file [green.worker_equipments]')
                exit(1)
            metrics.add("sector_resource", value=1, miner_id=miner_id, sector_id=sector, equipment=equipment)

            # GREEN METRICS ADD GLOBAL RESSOURCES TO ALL ACTIVE SECTORS
            metrics.add("sector_resource", value=1, miner_id=miner_id, sector_id=sector, equipment=green["worker_equipments"]["miner"])
            for equipment in green["global_infra_equipment"]:
                metrics.add("sector_resource", value=1, miner_id=miner_id, sector_id=sector, equipment=equipment)

    metrics.checkpoint("Sealing Sectors")

    sector_list_stripped = miner.get("SectorsListInStates", [["Proving", "Available"]])["result"]
    # remove duplicate sector ID (lotus bug)
    unique_sector_list = set(sector_list_stripped)

    metrics.checkpoint("GetListDiff")

    request_location = []
    miner_num=int(miner_id[2:])

    # We go though all sectors and enhanced them
    for i, sector in enumerate(unique_sector_list):
        # GREEN METRICS ADD GLOBAL RESSOURCES TO ALL ACTIVE SECTORS
        metrics.add("sector_resource", value=1, miner_id=miner_id, sector_id=sector, equipment=green["worker_equipments"]["miner"])
        for equipment in green["global_infra_equipment"]:
            metrics.add("sector_resource", value=1, miner_id=miner_id, sector_id=sector, equipment=equipment)

        # GREEN GENERATE THE LIST OF ALL STORAGE RESSOURCES TO RETRIEVE FOR LONGTERM SECTORS (PROVING | AVAILABLE)
        request_location.append(["StorageFindSector", [{"Miner":miner_num, "Number":sector}, 2, 0, False]])
        request_location.append(["StorageFindSector", [{"Miner":miner_num, "Number":sector}, 1, 0, False]])

    metrics.checkpoint("Proving Sectors")

    # We execute the batch
    location = miner.get_multiple(request_location)
    for loc in location:
        try:
            sector_id=loc["result"][0]["URLs"][0].split("-")[-1:][0]
            sector_type=loc["result"][0]["URLs"][0].split("/")[-2:-1][0]
            sector_storage_id=loc["result"][0]["ID"]
            sector_location=green["storage_equipments"][sector_storage_id]
            metrics.add("sector_resource", value=1, miner_id=miner_id, sector_id=sector_id, equipment=sector_location, sector_file_type=sector_type, storage_id=sector_storage_id)
        except Exception as exp:
            pass

    metrics.checkpoint("Storage")

def get_url_and_token(string):
    """ extract url and token from API format """
    try:
        [token, api] = string.split(":", 1)
        [_, _, addr, _, port, proto] = api.split("/", 5)
        url = f"{proto}://{addr}:{port}/rpc/v0"
    except Exception:
        raise ValueError(f"malformed API string : {string}")

    return (url, token)

def run(args, output):
    """Create all prerequisites object to collect"""

    # Load config file config.toml
    config_file = args.farcaster_config_folder.joinpath("config.toml")

    try:
        config = load_toml(config_file)
    except Exception as exp:
        raise exp

    # Verify that mandatory variable are in the config file
    for variable in "miner_api", "green":
        if variable not in config.keys():
            logging.error(f"{variable} not found in {config_file}")
            logging.info("Re-run the install.sh script or add it to the config file manually")
            sys.exit(0)

    with Metrics(output=output) as metrics:
        # Create the miner Object instance
        try:
            miner = Miner(*get_url_and_token(config["miner_api"]))
        except Exception as exp:
            raise MinerError("config value miner_ip " + str(exp))

        # Load addresses lookup config file to retrieve external wallet and vlookup
        addresses_config = load_toml(args.farcaster_config_folder.joinpath("addresses.toml"))

        # execute the collector
        collect(miner, metrics, addresses_config, config["green"])

def main():
    """ main function """

    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action='version', version=VERSION)
    parser.add_argument("--debug", action="store_true", help="Enable debug and python traceback")
    parser.add_argument("--log-level", default=os.environ.get("FARCASTER_LOG_LEVEL", "INFO"), help="Set log level")
    parser.add_argument("-c", "--farcaster-config-folder", default=Path.home().joinpath(".lotus-exporter-farcaster"), type=Path, help="Specifiy farcaster config path usually ~/.lotus-exporter-farcaster")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--file", help="output metrics to file")
    args = parser.parse_args()

    # Configure the logging output
    logging.basicConfig(format='%(levelname)s: %(message)s', level=getattr(logging, args.log_level.upper(), None))

    # In case output in a file, use a temporary file
    if args.file and args.file != "-":
        tmp_file = f"{args.file}$$"
        try:
            with open(tmp_file, "w") as f:
                run(args, output=f)
            os.rename(tmp_file, args.file)
        except Exception as exp:
            os.rename(tmp_file, args.file)
            logging.error(exp)
            sys.exit(1)

        return 0

    # If output to STDOUT
    try:
        run(args, output=sys.stdout)
    except Exception as exp:
        if args.debug:
            logging.error(traceback.format_exc())
        else:
            logging.error(exp)
        sys.exit(1)

if __name__ == "__main__":
    main()
