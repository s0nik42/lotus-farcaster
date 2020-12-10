#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=C0301, W0511, W0603, W0703, R0914, R0912, R0915
"""
@author: s0nik42
Copyright (c) 2020 Julien NOEL (s0nik42)

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

import urllib.request
from urllib.parse import urlparse
from pathlib import Path
import json
import time
import sys
import socket
import toml

VERSION = "v1.2.1-1"

#
# CONFIG VARIABLES // OPTIONAL THEY ARE NORMALLY AUTODETECTED
#
# Example : MINER_URL = "http://127.0.0.1:2345/rpc/v0"
MINER_URL = ""
# MINER_TOKEN is the content of the ~/.lotusminer/token file
MINER_TOKEN = ""
DAEMON_URL = ""
DAEMON_TOKEN = ""

###############################################################################
# DO NOT EDIT BELOW
###############################################################################

#################################################################################
# FUNCTIONS
#################################################################################

# REQUEST FUNCTIONS
def daemon_get_json(method, params):
    """Request daemon api"""
    return get_json(DAEMON_URL, DAEMON_TOKEN, method, params)

def miner_get_json(method, params):
    """ Request miner api"""
    return get_json(MINER_URL, MINER_TOKEN, method, params)

def get_json(url, token, method, params):
    """standard request api function"""
    jsondata = json.dumps({"jsonrpc": "2.0", "method": "Filecoin." + method, "params": params, "id": 3}).encode("utf8")
    req = urllib.request.Request(url)
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header("Content-Type", "application/json")

    try:
        response = urllib.request.urlopen(req, jsondata)
    except urllib.error.URLError as e_url:
        print(f'ERROR accessing { url } : { e_url.reason }', file=sys.stderr)
        print(f'DEBUG: method { method } / params { params } ', file=sys.stderr)
        print('lotus_scrape_execution_succeed { } 0')
        sys.exit(0)

    try:
        res = response.read()
        page = res.decode("utf8")

        # parse json object
        obj = json.loads(page)
    except Exception as e_generic:
        print(f'ERROR parsing URL response : { e_generic }', file=sys.stderr)
        print(f'DEBUG: method { method } / params { params } ', file=sys.stderr)
        print(f'DEBUG: { page } ', file=sys.stderr)
        print('lotus_scrape_execution_succeed { } 0')
        sys.exit(0)

    # Check if the answer contain results / otherwize quit
    if "result" not in obj.keys():
        print(f'ERROR { url } returned no result', file=sys.stderr)
        print(f'DEBUG: method { method } / params { params } ', file=sys.stderr)
        print(f'DEBUG: { obj } ', file=sys.stderr)

        # inform the dashboard execution failed
        print('lotus_scrape_execution_succeed { } 0')
        sys.exit(0)

    # output some object attributes
    return obj

def bitfield_count(bitfield):
    """Count bits from golang Bitfield object.
    s0nik42 reverse engineering
    https://github.com/filecoin-project/go-bitfield/blob/master/rle/rleplus.go#L88"""

    count = 0
    if len(bitfield) < 2:
        return 0
    for i in range(0, len(bitfield), 2):
        count += bitfield[i+1]
    return count

def printj(parsed):
    """JSON PRETTY PRINT"""
    print(json.dumps(parsed, indent=4, sort_keys=True))

START_TIME = 0
COLLECTOR_START_TIME = False
def checkpoint(collector_name):
    """ time measurement """
    global COLLECTOR_START_TIME
    if not COLLECTOR_START_TIME:
        COLLECTOR_START_TIME = START_TIME
        print("# HELP lotus_scrape_duration_seconds execution time of the different collectors")
        print("# TYPE lotus_scrape_duration_seconds gauge")
    print(f'lotus_scrape_duration_seconds {{ collector="{ collector_name}" }} {time.time() - COLLECTOR_START_TIME}')
    COLLECTOR_START_TIME = time.time()

def main():
    """ main function """

    global START_TIME, MINER_URL, MINER_TOKEN, DAEMON_URL, DAEMON_TOKEN

    # Start execution time mesurement
    START_TIME = time.time()

    # SET API IP PORT AND AUTH
    if MINER_URL == '':
        miner_config = toml.load(str(Path.home()) + "/.lotusminer/config.toml")
        miner_api_ip = "127.0.0.1"
        miner_api_port = "2345"
        # try to read configuration file to identify miner url
        if "API" in miner_config.keys():
            if "ListenAddress" in miner_config["API"].keys():
                miner_api = miner_config["API"]["ListenAddress"].split("/")
                miner_api_ip = miner_api[2].replace("0.0.0.0", "127.0.0.1")
                miner_api_port = miner_api[4]
        MINER_URL = "http://" + miner_api_ip + ":" + miner_api_port + "/rpc/v0"
    if DAEMON_URL == '':
        daemon_config = toml.load(str(Path.home()) + "/.lotus/config.toml")
        daemon_api_ip = "127.0.0.1"
        daemon_api_port = "1234"
        # try to read configuration file to identify daemon url
        if "API" in daemon_config.keys():
            if "ListenAddress" in daemon_config["API"].keys():
                daemon_api = daemon_config["API"]["ListenAddress"].split("/")
                daemon_api_ip = daemon_api[2].replace("0.0.0.0", "127.0.0.1")
                daemon_api_port = daemon_api[4]
        DAEMON_URL = "http://" + daemon_api_ip + ":" + daemon_api_port + "/rpc/v0"

    if MINER_TOKEN == '':
        with open(str(Path.home()) + "/.lotusminer/token", "r") as text_file:
            MINER_TOKEN = text_file.read()
    if DAEMON_TOKEN == '':
        with open(str(Path.home()) + "/.lotus/token", "r") as text_file:
            DAEMON_TOKEN = text_file.read()
    #################################################################################
    # MAIN
    #################################################################################

    # SCRAPE METRIC DEFINITION
    print("# HELP lotus_scrape_execution_succeed return 1 if lotus-farcaster execution was successfully")
    print("# TYPE lotus_scrape_execution_succeed gauge")

    # LOCAL TIME METRIC
    print("# HELP lotus_local_time time on the node machine when last execution start in epoch")
    print("# TYPE lotus_local_time gauge")
    print(f'lotus_local_time {{ }} { int(time.time()) }')

    # RETRIEVE MINER ID
    actoraddress = miner_get_json("ActorAddress", [])
    miner_id = actoraddress['result']

    # RETRIEVE TIPSET + CHAINHEAD
    chainhead = daemon_get_json("ChainHead", [])
    tipsetkey = chainhead["result"]["Cids"]
    # XXX small hack trying to speedup the script
    empty_tipsetkey = []
    print("# HELP lotus_chain_height return current height")
    print("# TYPE lotus_chain_height counter")
    print(f'lotus_chain_height {{ miner_id="{miner_id}" }} {chainhead["result"]["Height"]}')
    checkpoint("ChainHead")

    # GENERATE CHAIN SYNC STATUS
    print("# HELP lotus_chain_sync_diff return daemon sync height diff with chainhead for each daemon worker")
    print("# TYPE lotus_chain_sync_diff  gauge")
    print("# HELP lotus_chain_sync_status return daemon sync status with chainhead for each daemon worker")
    print("# TYPE lotus_chain_sync_status  gauge")
    sync_status = daemon_get_json("SyncState", [])
    for worker in sync_status["result"]["ActiveSyncs"]:
        try:
            diff_height = worker["Target"]["Height"] - worker["Base"]["Height"]
        except Exception:
            diff_height = -1
        print(f'lotus_chain_sync_diff {{ miner_id="{ miner_id }", worker_id="{ sync_status["result"]["ActiveSyncs"].index(worker) }" }} { diff_height }')
        print(f'lotus_chain_sync_status {{ miner_id="{ miner_id }", worker_id="{ sync_status["result"]["ActiveSyncs"].index(worker) }" }} { worker["Stage"]  }')
    checkpoint("ChainSync")

    # GENERATE MINER INFO
    miner_version = miner_get_json("Version", [])
    checkpoint("Miner")

    # RETRIEVE MAIN ADDRESSES
    daemon_stats = daemon_get_json("StateMinerInfo", [miner_id, empty_tipsetkey])
    miner_owner = daemon_stats["result"]["Owner"]
    miner_owner_addr = daemon_get_json("StateAccountKey", [miner_owner, empty_tipsetkey])["result"]
    miner_worker = daemon_stats["result"]["Worker"]
    miner_worker_addr = daemon_get_json("StateAccountKey", [miner_worker, empty_tipsetkey])["result"]
    try:
        miner_control0 = daemon_stats["result"]["ControlAddresses"][0]
    except:
        miner_control0 = miner_worker
    miner_control0_addr = daemon_get_json("StateAccountKey", [miner_control0, empty_tipsetkey])["result"]

    print("# HELP lotus_miner_info lotus miner information like adress version etc")
    print("# TYPE lotus_miner_info gauge")
    print("# HELP lotus_miner_info_sector_size lotus miner sector size")
    print("# TYPE lotus_miner_info_sector_size gauge")
    print(f'lotus_miner_info {{ miner_id = "{miner_id}", version="{ miner_version["result"]["Version"] }", owner="{ miner_owner }", owner_addr="{ miner_owner_addr }", worker="{ miner_worker }", worker_addr="{ miner_worker_addr }", control0="{ miner_control0 }", control0_addr="{ miner_control0_addr }" }} 1')
    print(f'lotus_miner_info_sector_size {{ miner_id = "{miner_id}" }} { daemon_stats["result"]["SectorSize"] }')
    checkpoint("StateMinerInfo")

    # GENERATE DAEMON INFO
    daemon_network = daemon_get_json("StateNetworkName", [])
    daemon_network_version = daemon_get_json("StateNetworkVersion", [empty_tipsetkey])
    daemon_version = daemon_get_json("Version", [])
    print("# HELP lotus_info lotus daemon information like adress version, value is set to network version number")
    print("# TYPE lotus_info gauge")
    print(f'lotus_info {{ miner_id="{miner_id}", version="{ daemon_version["result"]["Version"] }", network="{ daemon_network["result"] }"}} { daemon_network_version["result"]}')
    checkpoint("Daemon")

    # GENERATE WALLET + LOCKED FUNDS BALANCES
    walletlist = daemon_get_json("WalletList", [])
    print("# HELP lotus_wallet_balance return wallet balance")
    print("# TYPE lotus_wallet_balance gauge")
    for addr in walletlist["result"]:
        balance = daemon_get_json("WalletBalance", [addr])
        short = addr[0:5] + "..." + addr[-5:]
        print(f'lotus_wallet_balance {{ miner_id="{miner_id}", address="{ addr }", short="{ short }" }} { int(balance["result"])/1000000000000000000 }')

    # Add miner balance :
    miner_balance_available = daemon_get_json("StateMinerAvailableBalance", [miner_id, empty_tipsetkey])
    print(f'lotus_wallet_balance {{ miner_id="{miner_id}", address="{ miner_id }", short="{ miner_id }" }} { int(miner_balance_available["result"])/1000000000000000000 }')

    # Retrieve locked funds balance
    locked_funds = daemon_get_json("StateReadState", [miner_id, empty_tipsetkey])
    print("# HELP lotus_wallet_locked_balance return miner wallet locked funds")
    print("# TYPE lotus_wallet_locked_balance gauge")
    for i in ["PreCommitDeposits", "LockedFunds", "FeeDebt", "InitialPledge"]:
        print(f'lotus_wallet_locked_balance {{ miner_id="{miner_id}", address="{ miner_id }", locked_type ="{ i }" }} { int(locked_funds["result"]["State"][i])/1000000000000000000 }')
    checkpoint("Balances")

    # GENERATE POWER
    powerlist = daemon_get_json("StateMinerPower", [miner_id, empty_tipsetkey])
    print("# HELP lotus_power return miner power")
    print("# TYPE lotus_power gauge")
    for minerpower in powerlist["result"]["MinerPower"]:
        print(f'lotus_power {{ miner_id="{miner_id}", scope="miner", power_type="{ minerpower }" }} { powerlist["result"]["MinerPower"][minerpower] }')
    for totalpower in powerlist["result"]["TotalPower"]:
        print(f'lotus_power {{ miner_id="{miner_id}", scope="network", power_type="{ totalpower }" }} { powerlist["result"]["TotalPower"][totalpower] }')

    # Mining eligibility
    print("# HELP lotus_power_mining_eligibility return miner mining eligibility")
    print("# TYPE lotus_power_mining_eligibility gauge")
    base_info = daemon_get_json("MinerGetBaseInfo", [miner_id, chainhead["result"]["Height"], tipsetkey])

    if base_info["result"] is None:
        print(f'ERROR MinerGetBaseInfo return no result', file=sys.stderr)
        print(f'KNOWN_REASON your miner reports wrong info to the chain and thats pretty bad (not just for the dashboard)', file=sys.stderr)
        print(f'SOLUTION restart your miner and node', file=sys.stderr)
        print('lotus_scrape_execution_succeed { } 0')
        sys.exit(0)

    if base_info["result"]["EligibleForMining"]:
        eligibility = 1
    else:
        eligibility = 0
    print(f'lotus_power_mining_eligibility {{ miner_id="{miner_id}" }} { eligibility }')
    checkpoint("Power")

    # GENERATE MPOOL
    mpoolpending = daemon_get_json("MpoolPending", [empty_tipsetkey])
    print("# HELP lotus_mpool_total return number of message pending in mpool")
    print("# TYPE lotus_mpool_total gauge")
    print("# HELP lotus_mpool_local_total return total number in mpool comming from local adresses")
    print("# TYPE lotus_power_local_total gauge")
    print("# HELP lotus_mpool_local_message local message details")
    print("# TYPE lotus_mpool_local_message gauge")
    mpool_total = 0
    mpool_local_total = 0
    for message in mpoolpending["result"]:
        mpool_total += 1
        frm = message["Message"]["From"]
        if frm in walletlist["result"]:
            mpool_local_total += 1
            if frm == miner_owner_addr:
                display_addr = "owner"
            elif frm == miner_worker_addr:
                display_addr = "worker"
            elif frm == miner_control0_addr:
                display_addr = "control0"
            elif frm != miner_id:
                display_addr = frm[0:5] + "..." + frm[-5:]
            print(f'lotus_mpool_local_message {{ miner_id="{miner_id}", from="{ display_addr }", to="{ message["Message"]["To"] }", nonce="{ message["Message"]["Nonce"] }", value="{ message["Message"]["Value"] }", gaslimit="{ message["Message"]["GasLimit"] }", gasfeecap="{ message["Message"]["GasFeeCap"] }", gaspremium="{ message["Message"]["GasPremium"] }", method="{ message["Message"]["Method"] }" }} 1')

    print(f'lotus_mpool_total {{ miner_id="{miner_id}" }} { mpool_total }')
    print(f'lotus_mpool_local_total {{ miner_id="{miner_id}" }} { mpool_local_total }')
    checkpoint("MPool")

    # GENERATE NET_PEERS
    daemon_netpeers = daemon_get_json("NetPeers", [])
    print("# HELP lotus_netpeers_total return number netpeers")
    print("# TYPE lotus_netpeers_total gauge")
    print(f'lotus_netpeers_total {{ miner_id="{miner_id}" }} { len(daemon_netpeers["result"]) }')

    miner_netpeers = miner_get_json("NetPeers", [])
    print("# HELP lotus_miner_netpeers_total return number netpeers")
    print("# TYPE lotus_miner_netpeers_total gauge")
    print(f'lotus_miner_netpeers_total {{ miner_id="{miner_id}" }} { len(miner_netpeers["result"]) }')
    checkpoint("NetPeers")

    # GENERATE NETSTATS XXX Verfier la qualité des stats ... lotus net, API et Grafana sont tous differents
    print("# HELP lotus_net_protocol_in return input net per protocol")
    print("# TYPE lotus_net_protocol_in counter")
    print("# HELP lotus_net_protocol_out return output per protocol net")
    print("# TYPE lotus_net_protocol_out counter")
    protocols_list = daemon_get_json("NetBandwidthStatsByProtocol", [])
    for protocol in protocols_list["result"]:
        print(f'lotus_net_protocol_in {{ miner_id="{miner_id}", protocol="{ protocol }" }} { protocols_list["result"][protocol]["TotalIn"] }')
        print(f'lotus_net_protocol_out {{ miner_id="{miner_id}", protocol="{ protocol }" }} { protocols_list["result"][protocol]["TotalOut"] }')

    print("# HELP lotus_miner_net_protocol_in return input net per protocol")
    print("# TYPE lotus_miner_net_protocol_in counter")
    print("# HELP lotus_miner_net_protocol_out return output per protocol net")
    print("# TYPE lotus_miner_net_protocol_out counter")
    protocols_list = miner_get_json("NetBandwidthStatsByProtocol", [])
    for protocol in protocols_list["result"]:
        print(f'lotus_miner_net_protocol_in {{ miner_id="{miner_id}", protocol="{ protocol }" }} { protocols_list["result"][protocol]["TotalIn"] }')
        print(f'lotus_miner_net_protocol_out {{ miner_id="{miner_id}", protocol="{ protocol }" }} { protocols_list["result"][protocol]["TotalOut"] }')

    print("# HELP lotus_net_total_in return input net")
    print("# TYPE lotus_net_total_in counter")
    print("# HELP lotus_net_total_out return output net")
    print("# TYPE lotus_net_total_out counter")
    net_list = daemon_get_json("NetBandwidthStats", [])
    print(f'lotus_net_total_in {{ miner_id="{miner_id}" }} { net_list["result"]["TotalIn"] }')
    print(f'lotus_net_total_out {{ miner_id="{miner_id}" }} { net_list["result"]["TotalOut"] }')

    print("# HELP lotus_miner_net_total_in return input net")
    print("# TYPE lotus_miner_net_total_in counter")
    print("# HELP lotus_miner_net_total_out return output net")
    print("# TYPE lotus_miner_net_total_out counter")
    net_list = miner_get_json("NetBandwidthStats", [])
    print(f'lotus_miner_net_total_in {{ miner_id="{miner_id}" }} { net_list["result"]["TotalIn"] }')
    print(f'lotus_miner_net_total_out {{ miner_id="{miner_id}" }} { net_list["result"]["TotalOut"] }')
    checkpoint("NetBandwidth")

    # GENERATE WORKER INFOS
    workerstats = miner_get_json("WorkerStats", [])
    # XXX 1.2.1 introduce a new worker_id format. Later we should delete it, its a useless info.
    #print("# HELP lotus_miner_worker_id All lotus worker information prfer to use workername than workerid which is changing at each restart")
    #print("# TYPE lotus_miner_worker_id gauge")
    print("# HELP lotus_miner_worker_mem_physical_used worker minimal memory used")
    print("# TYPE lotus_miner_worker_mem_physical_used gauge")
    print("# HELP lotus_miner_worker_mem_vmem_used worker maximum memory used")
    print("# TYPE lotus_miner_worker_mem_vmem_used gauge")
    print("# HELP lotus_miner_worker_mem_reserved worker memory reserved by lotus")
    print("# TYPE lotus_miner_worker_mem_reserved gauge")
    print("# HELP lotus_miner_worker_gpu_used is the GPU used by lotus")
    print("# TYPE lotus_miner_worker_gpu_used gauge")
    print("# HELP lotus_miner_worker_cpu_used number of CPU used by lotus")
    print("# TYPE lotus_miner_worker_cpu_used gauge")
    print("# HELP lotus_miner_worker_cpu number of CPU")
    print("# TYPE lotus_miner_worker_cpu gauge")
    print("# HELP lotus_miner_worker_gpu number of GPU")
    print("# TYPE lotus_miner_worker_gpu gauge")
    print("# HELP lotus_miner_worker_mem_physical server RAM")
    print("# TYPE lotus_miner_worker_mem_physical gauge")
    print("# HELP lotus_miner_worker_mem_swap server SWAP")
    print("# TYPE lotus_miner_worker_mem_swap gauge")
    for val in workerstats["result"].items():
        val = val[1]
        info = val["Info"]
        worker_host = info["Hostname"]
        mem_physical = info["Resources"]["MemPhysical"]
        mem_swap = info["Resources"]["MemSwap"]
        mem_reserved = info["Resources"]["MemReserved"]
        cpus = info["Resources"]["CPUs"]
        gpus = len(info["Resources"]["GPUs"])
        mem_used_min = val["MemUsedMin"]
        mem_used_max = val["MemUsedMax"]
        if val["GpuUsed"]:
            gpu_used = 1
        else:
            gpu_used = 0
        cpu_used = val["CpuUse"]

        print(f'lotus_miner_worker_cpu {{ miner_id="{miner_id}", worker_host="{worker_host}" }} { cpus }')
        print(f'lotus_miner_worker_gpu {{ miner_id="{miner_id}", worker_host="{worker_host}" }} { gpus }')
        print(f'lotus_miner_worker_mem_physical {{ miner_id="{miner_id}", worker_host="{worker_host}" }} { mem_physical }')
        print(f'lotus_miner_worker_mem_swap {{ miner_id="{miner_id}", worker_host="{worker_host}" }} { mem_swap }')
        print(f'lotus_miner_worker_mem_physical_used {{ miner_id="{miner_id}", worker_host="{worker_host}" }} {mem_used_min}')
        print(f'lotus_miner_worker_mem_vmem_used {{ miner_id="{miner_id}", worker_host="{worker_host}" }} {mem_used_max}')
        print(f'lotus_miner_worker_mem_reserved {{ miner_id="{miner_id}", worker_host="{worker_host}" }} {mem_reserved}')
        print(f'lotus_miner_worker_gpu_used {{ miner_id="{miner_id}", worker_host="{worker_host}" }} {gpu_used}')
        print(f'lotus_miner_worker_cpu_used {{ miner_id="{miner_id}", worker_host="{worker_host}" }} {cpu_used}')
    checkpoint("Workers")

    # GENERATE JOB INFOS
    workerjobs = miner_get_json("WorkerJobs", [])
    print("# HELP lotus_miner_worker_job status of each individual job running on the workers. Value is the duration")
    print("# TYPE lotus_miner_worker_job gauge")
    for (wrk, job_list) in workerjobs["result"].items():
        for job in job_list:
            job_id = job['ID']['ID']
            sector = str(job['Sector']['Number'])

            try:
                worker_host = workerstats["result"][wrk]["Info"]["Hostname"]
            except:
                # sometime WorkerJobs return invalid worker_id like 0000-000000-0000... in that case return unknown
                worker_host = "unknown"
            task = str(job['Task'])
            job_start_time = str(job['Start'])
            run_wait = str(job['RunWait'])
            job_start_epoch = time.mktime(time.strptime(job_start_time[:19], '%Y-%m-%dT%H:%M:%S'))
            print(f'lotus_miner_worker_job {{ miner_id="{miner_id}", job_id="{job_id}", worker_host="{ worker_host }", task="{task}", sector_id="{sector}", job_start_time="{job_start_time}", run_wait="{run_wait}" }} { START_TIME - job_start_epoch }')
    checkpoint("Jobs")

    # GENERATE JOB SCHEDDIAG
    scheddiag = miner_get_json("SealingSchedDiag", [True])

    if scheddiag["result"]["SchedInfo"]["Requests"]:
        for req in scheddiag["result"]["SchedInfo"]["Requests"]:
            sector = req["Sector"]["Number"]
            task = req["TaskType"]
            print(f'lotus_miner_worker_job {{ miner_id="{miner_id}", job_id="", worker="", task="{task}", sector_id="{sector}", start="", run_wait="99" }} 0')
    checkpoint("SchedDiag")

    # GENERATE SECTORS
    print("# HELP lotus_miner_sector_state sector state")
    print("# TYPE lotus_miner_sector_state gauge")
    print("# HELP lotus_miner_sector_event contains important event of the sector life")
    print("# TYPE lotus_miner_sector_event gauge")
    print("# HELP lotus_miner_sector_sealing_deals_info contains information related to deals that are not in Proving and Removed state.")
    print("# TYPE lotus_miner_sector_sealing_deals_info gauge")

    sector_list = miner_get_json("SectorsList", [])
    #sectors_counters = {}
    # remove duplicate (bug)
    unique_sector_list = set(sector_list["result"])
    for sector in unique_sector_list:
        detail = miner_get_json("SectorsStatus", [sector, False])
        deals = len(detail["result"]["Deals"])-detail["result"]["Deals"].count(0)
        creation_date = detail["result"]["Log"][0]["Timestamp"]
        packed_date = ""
        finalized_date = ""
        verified_weight = detail["result"]["VerifiedDealWeight"]
        for log in range(len(detail["result"]["Log"])):
            if detail["result"]["Log"][log]["Kind"] == "event;sealing.SectorPacked":
                packed_date = detail["result"]["Log"][log]["Timestamp"]
            if detail["result"]["Log"][log]["Kind"] == "event;sealing.SectorFinalized":
                finalized_date = detail["result"]["Log"][log]["Timestamp"]
        if detail["result"]["Log"][0]["Kind"] == "event;sealing.SectorStartCC":
            pledged = 1
        else:
            pledged = 0
        print(f'lotus_miner_sector_state {{ miner_id="{miner_id}", sector_id="{ sector }", state="{ detail["result"]["State"] }", pledged="{ pledged }", deals="{ deals }", verified_weight="{ verified_weight }" }} 1')

        if packed_date != "":
            print(f'lotus_miner_sector_event {{ miner_id="{miner_id}", sector_id="{ sector }", event_type="packed" }} { packed_date }')
        if creation_date != "":
            print(f'lotus_miner_sector_event {{ miner_id="{miner_id}", sector_id="{ sector }", event_type="creation" }} { creation_date }')
        if finalized_date != "":
            print(f'lotus_miner_sector_event {{ miner_id="{miner_id}", sector_id="{ sector }", event_type="finalized" }} { finalized_date }')

        if detail["result"]["State"] not in ["Proving", "Removed"]:
            for deal in detail["result"]["Deals"]:
                if deal != 0:
                    try:
                        deal_info = daemon_get_json("StateMarketStorageDeal", [deal, empty_tipsetkey])
                    except:
                        deal_is_verified = "unknown"
                        deal_size = "unknown"
                        deal_slash_epoch = "unknown"
                        deal_price_per_epoch = "unknown"
                        deal_provider_collateral = "unknown"
                        deal_client_collateral = "unknown"
                        deal_start_epoch = "unknown"
                        deal_end_epoch = "unknown"
                    else:
                        deal_is_verified = deal_info["result"]["Proposal"]["VerifiedDeal"]
                        deal_size = deal_info["result"]["Proposal"]["PieceSize"]
                        deal_slash_epoch = deal_info["result"]["State"]["SlashEpoch"]
                        deal_price_per_epoch = deal_info["result"]["Proposal"]["StoragePricePerEpoch"]
                        deal_provider_collateral = deal_info["result"]["Proposal"]["ProviderCollateral"]
                        deal_client_collateral = deal_info["result"]["Proposal"]["ClientCollateral"]
                        deal_start_epoch = deal_info["result"]["Proposal"]["StartEpoch"]
                        deal_end_epoch = deal_info["result"]["Proposal"]["EndEpoch"]
                    print(f'lotus_miner_sector_sealing_deals_size {{ miner_id="{miner_id}", sector_id="{ sector }", deal_id="{ deal }", deal_is_verified="{ deal_is_verified }", deal_slash_epoch="{ deal_slash_epoch }", deal_price_per_epoch="{ deal_price_per_epoch }",deal_provider_collateral="{ deal_provider_collateral }", deal_client_collateral="{ deal_client_collateral }", deal_size="{ deal_size }", deal_start_epoch="{ deal_start_epoch }", deal_end_epoch="{ deal_end_epoch }" }} 1')

    # GENERATE DEADLINES
    proven_partitions = daemon_get_json("StateMinerDeadlines", [miner_id, empty_tipsetkey])
    deadlines = daemon_get_json("StateMinerProvingDeadline", [miner_id, empty_tipsetkey])
    dl_epoch = deadlines["result"]["CurrentEpoch"]
    dl_index = deadlines["result"]["Index"]
    dl_open = deadlines["result"]["Open"]
    dl_numbers = deadlines["result"]["WPoStPeriodDeadlines"]
    dl_window = deadlines["result"]["WPoStChallengeWindow"]
    print("# HELP lotus_miner_deadline_info deadlines and WPoSt informations")
    print("# TYPE lotus_miner_deadline_info gauge")
    print(f'lotus_miner_deadline_info {{ miner_id="{miner_id}", current_idx="{ dl_index }", current_epoch="{ dl_epoch }",current_open_epoch="{ dl_open }", wpost_period_deadlines="{ dl_numbers }", wpost_challenge_window="{ dl_window }" }} 1')
    print("# HELP lotus_miner_deadline_active_start remaining time before deadline start")
    print("# TYPE lotus_miner_deadline_active_start gauge")
    print("# HELP lotus_miner_deadline_active_sectors_all number of sectors in the deadline")
    print("# TYPE lotus_miner_deadline_active_sectors_all gauge")
    print("# HELP lotus_miner_deadline_active_sectors_recovering number of sectors in recovering state")
    print("# TYPE lotus_miner_deadline_active_sectors_recovering gauge")
    print("# HELP lotus_miner_deadline_active_sectors_faulty number of faulty sectors")
    print("# TYPE lotus_miner_deadline_active_sectors_faulty gauge")
    print("# HELP lotus_miner_deadline_active_sectors_live number of live sectors")
    print("# TYPE lotus_miner_deadline_active_sectors_live gauge")
    print("# HELP lotus_miner_deadline_active_sectors_active number of active sectors")
    print("# TYPE lotus_miner_deadline_active_sectors_active gauge")
    print("# HELP lotus_miner_deadline_active_partitions number of partitions in the deadline")
    print("# TYPE lotus_miner_deadline_active_partitions gauge")
    print("# HELP lotus_miner_deadline_active_partitions_proven number of partitions already proven for the deadline")
    print("# TYPE lotus_miner_deadline_active_partitions_proven gauge")
    for c_dl in range(dl_numbers):
        idx = (dl_index + c_dl) % dl_numbers
        opened = dl_open + dl_window * c_dl
        partitions = daemon_get_json("StateMinerPartitions", [miner_id, idx, empty_tipsetkey])
        if partitions["result"]:
            faulty = 0
            recovering = 0
            alls = 0
            active = 0
            live = 0
            count = len(partitions["result"])
            proven = bitfield_count(proven_partitions["result"][idx]["PostSubmissions"])
            for partition in partitions["result"]:
                faulty += bitfield_count(partition["FaultySectors"])
                recovering += bitfield_count(partition["RecoveringSectors"])
                active += bitfield_count(partition["ActiveSectors"])
                live += bitfield_count(partition["LiveSectors"])
                alls = bitfield_count(partition["AllSectors"])
            print(f'lotus_miner_deadline_active_start {{ miner_id="{miner_id}", index="{ idx }" }} { (opened - dl_epoch) * 30  }')
            print(f'lotus_miner_deadline_active_partitions_proven {{ miner_id="{miner_id}", index="{ idx }" }} { proven }')
            print(f'lotus_miner_deadline_active_partitions {{ miner_id="{miner_id}", index="{ idx }" }} { count }')
            print(f'lotus_miner_deadline_active_sectors_all {{ miner_id="{miner_id}", index="{ idx }" }} { alls  }')
            print(f'lotus_miner_deadline_active_sectors_recovering {{ miner_id="{miner_id}", index="{ idx }" }} { recovering }')
            print(f'lotus_miner_deadline_active_sectors_faulty {{ miner_id="{miner_id}", index="{ idx }" }} { faulty }')
            print(f'lotus_miner_deadline_active_sectors_active {{ miner_id="{miner_id}", index="{ idx }" }} { active }')
            print(f'lotus_miner_deadline_active_sectors_live {{ miner_id="{miner_id}", index="{ idx }" }} { live }')
    checkpoint("Deadlines")

    # GENERATE STORAGE INFO
    print("# HELP lotus_miner_storage_info get storage info state")
    print("# TYPE lotus_miner_storage_info gauge")
    print("# HELP lotus_miner_storage_capacity get storage total capacity")
    print("# TYPE lotus_miner_storage_capacity gauge")
    print("# HELP lotus_miner_storage_available get storage available capacity")
    print("# TYPE lotus_miner_storage_available gauge")
    print("# HELP lotus_miner_storage_reserved get storage reserved capacity")
    print("# TYPE lotus_miner_storage_reserved  gauge")
    storage_list = miner_get_json("StorageList", [])

    storage_local_list = miner_get_json("StorageLocal", [])
    for storage in storage_list["result"].keys():
        storage_info = miner_get_json("StorageInfo", [storage])
        if storage in storage_local_list["result"].keys():
            storage_path = storage_local_list["result"][storage]
        else:
            storage_path = ''
        storage_id = storage_info["result"]["ID"]
        storage_url = urlparse(storage_info["result"]["URLs"][0])
        storage_host_ip = storage_url.hostname
        try:
            storate_host_name = socket.gethostbyaddr(storage_host_ip)[0]
        except Exception:
            storate_host_name = storage_host_ip

        storage_host_port = storage_url.port
        storage_weight = storage_info["result"]["Weight"]
        storage_can_seal = storage_info["result"]["CanSeal"]
        storage_can_store = storage_info["result"]["CanStore"]
        try:
            storage_stat = miner_get_json("StorageStat", [storage])
        except:
            storage_capacity = 0
            storage_available = 0
            storage_reserved = 0
        else:
            storage_capacity = storage_stat["result"]["Capacity"]
            storage_available = storage_stat["result"]["Available"]
            storage_reserved = storage_stat["result"]["Reserved"]
        print(f'lotus_miner_storage_info {{ miner_id="{miner_id}", storage_id="{ storage_id }", storage_url="{ storage_info["result"]["URLs"][0] }", storage_host_name="{ storate_host_name }", storage_host_ip="{ storage_host_ip }", storage_host_port="{ storage_host_port }", weight="{ storage_weight }", can_seal="{ storage_can_seal }", can_store="{ storage_can_store }", path="{ storage_path }" }} 1')
        print(f'lotus_miner_storage_capacity {{ miner_id="{miner_id}", storage_id="{ storage_id }" }} { storage_capacity }')
        print(f'lotus_miner_storage_available {{ miner_id="{miner_id}", storage_id="{ storage_id }" }} { storage_available }')
        print(f'lotus_miner_storage_reserved {{ miner_id="{miner_id}", storage_id="{ storage_id }" }} { storage_reserved }')
    checkpoint("Storage")

    # GENERATE SCRAPE TIME
    print(f'lotus_scrape_duration_seconds {{ collector="All" }} {time.time() - START_TIME}')
    print('lotus_scrape_execution_succeed { } 1')

    # XXX TODO
    # GENERATE STORAGE MARKET
    #print(miner_get_json("MarketGetAsk",[]))
    #print(miner_get_json("DealsConsiderOnlineStorageDeals",[]))
    #print(miner_get_json("DealsConsiderOfflineStorageDeals",[]))
    #print(miner_get_json("DealsConsiderOnlineRetrievalDeals",[]))
    #print(miner_get_json("DealsConsiderOfflineRetrievalDeals",[]))
    #print(miner_get_json("SectorGetSealDelay",[]))
    #print(miner_get_json("MarketListDeals",[]))

    # GENERATE RETRIEVAL MARKET
    #print(miner_get_json("MarketGetRetrievalAsk",[]))
    #print(miner_get_json("MarketListRetrievalDeals",[]))

    # GENERATE DATA TRANSFERS
    #print(miner_get_json("MarketListDataTransfers",[]))

    # XXX rajouter les errors de sectors
    #print(daemon_get_json("StateMinerFaults",[miner_id,empty_tipsetkey]))
    # GAs price
    # XXX Display SectorGetSealDelay / XXX Display sealing Sectors and details
    # Winning blocks
    # WaitDeal (list of deals/ Since / SealWaitingTime)
    # XXX LA PoST n'impact pas l'etat les ressources des MAchines voir pour changer ca
    # Gerer une metrics : service UP/DOWN
    # XXX TROUVER LA LISTE DES FAULTY SECTORS
    # XXX A quoi correcpond le champs retry dans le SectorStatus

# XXX Review Schediag // Structure completely changed
# XXX Parse version : https://stackoverflow.com/questions/11887762/how-do-i-compare-version-numbers-in-python
# XXX Include Verified Deals in the Committed PowerCalculation
# XXX Gerer le bug lier à l'absence de Worker (champs GPU vide, etc...)
if __name__ == "__main__":
    # execute only if run as a script
    main()
