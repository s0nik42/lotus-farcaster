#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=C0301, W0511, W0603, W0703, R0914, R0912, R0915, R0902, R0201, C0302, C0103
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
# Release v2
#   - Object oriented code
#   - Added basefee
#   - lookup known addresses
#   - Add message type and actor type on mpool
#   - Add verified datacap dashboard
#   - Add Max quality adjusted power
#   - Add Client name (inc lookup) in Sealing Deals
#   - Sector state in deadline table
#   - Sectors with deals Chart and History
#   - Add external wallet support
#   - Performance improved : scrape time /3 using aiohttp
#   - Fil+ Realtime and Historical view of Datacap allocated to the miner addresses
#   - Implementation of Max Quality Adjusted Power
#   - Farcaster Status
#   - Deployment toolset
#   - Support seamless network upgrade, resolving actor_code change. (implies using py-multibase)
# v2.0.3:
#   - Trigger exception when api return no result
# Futur Release v3
#   - Add Deal transfer

from urllib.parse import urlparse
from pathlib import Path
import json
import time
import sys
import socket
import os
import asyncio
import aiohttp
import toml
import multibase

VERSION = "v2.0.3"

#
# OVERRIDE AUTODETECTED CONFIG VALUES (should only be used if autodetection is failling)
#
# Example : MINER_URL = "http://127.0.0.1:2345/rpc/v0"
MINER_URL = ""
MINER_TOKEN = ""
DAEMON_URL = ""
DAEMON_TOKEN = ""

#################################################################################
# DO NOT EDIT BELOW
#################################################################################

#################################################################################
# CLASS DEFINITION
#################################################################################

class MinerError(Exception):
    """Customer Exception to identify error coming from the miner. Used  for the dashboard Status panel"""

class DaemonError(Exception):
    """Customer Exception to identify error coming from the miner. Used  for the dashboard Status panel"""

class Lotus:
    """This class manages all interaction with lotus API miner and daemon"""
    __tipset_key = None
    __chain_head = None
    __basefee = None
    __local_wallet_list = None
    miner_id = None
    miner_url = None
    daemon_url = None
    miner_token = None
    daemon_token = None
    known_addresses = {}

    message_type = {"Account":
                        [
                            "Constructor",
                            "PubkeyAddress"],
                    "Init":
                        [
                            "Constructor",
                            "Exec"],
                    "Cron":
                        [
                            "Constructor",
                            "EpochTick"],
                    "Reward":
                        [
                            "Constructor",
                            "AwardBlockReward",
                            "ThisEpochReward",
                            "UpdateNetworkKPI"],
                    "Multisig":
                        [
                            "Constructor",
                            "Propose",
                            "Approve",
                            "Cancel",
                            "AddSigner",
                            "RemoveSigner",
                            "SwapSigner",
                            "ChangeNumApprovalsThreshold",
                            "LockBalance"],
                    "PaymentChannel":
                        [
                            "Constructor",
                            "UpdateChannelState",
                            "Settle",
                            "Collect"],
                    "StorageMarket":
                        [
                            "Constructor",
                            "AddBalance",
                            "WithdrawBalance",
                            "PublishStorageDeals",
                            "VerifyDealsForActivation",
                            "ActivateDeals",
                            "OnMinerSectorsTerminate",
                            "ComputeDataCommitment",
                            "CronTick"],
                    "StoragePower":
                        [
                            "Constructor",
                            "CreateMiner",
                            "UpdateClaimedPower",
                            "EnrollCronEvent",
                            "OnEpochTickEnd",
                            "UpdatePledgeTotal",
                            "Deprecated1",
                            "SubmitPoRepForBulkVerify",
                            "CurrentTotalPower"],
                    "StorageMiner":
                        [
                            "Constructor",
                            "ControlAddresses",
                            "ChangeWorkerAddress",
                            "ChangePeerID",
                            "SubmitWindowedPoSt",
                            "PreCommitSector",
                            "ProveCommitSector",
                            "ExtendSectorExpiration",
                            "TerminateSectors",
                            "DeclareFaults",
                            "DeclareFaultsRecovered",
                            "OnDeferredCronEvent",
                            "CheckSectorProven",
                            "ApplyRewards",
                            "ReportConsensusFault",
                            "WithdrawBalance",
                            "ConfirmSectorProofsValid",
                            "ChangeMultiaddrs",
                            "CompactPartitions",
                            "CompactSectorNumbers",
                            "ConfirmUpdateWorkerKey",
                            "RepayDebt",
                            "ChangeOwnerAddress",
                            "DisputeWindowedPoSt"],

                    "VerifiedRegistry":
                        [
                            "Constructor",
                            "AddVerifier",
                            "RemoveVerifier",
                            "AddVerifiedClient",
                            "UseBytes",
                            "RestoreBytes"]
                    }

    actor_type = {
        b"system":           "System",
        b"init":             "Init",
        b"reward":           "Reward",
        b"cron":             "Cron",
        b"storagepower":     "StoragePower",
        b"storagemarket":    "StorageMarket",
        b"verifiedregistry": "VerifiedRegistry",
        b"account":          "Account",
        b"multisig":         "Multisig",
        b"paymentchannel":   "PaymentChannel",
        b"storageminer":     "StorageMiner"
    }

    def __init__(self, miner_url="", miner_token="", daemon_url="", daemon_token=""):
        # Generate API URL (auto/manual)
        if miner_url == '':
            try:
                with open(str(Path.home()) + "/.lotusminer/api", "r") as text_file:
                    miner_api_line = text_file.read()
            except Exception  as e_generic:
                raise MinerError(e_generic)

            miner_api = miner_api_line.split("/")
            miner_api_ip = miner_api[2]
            miner_api_port = miner_api[4]
            self.miner_url = "http://" + miner_api_ip + ":" + miner_api_port + "/rpc/v0"
        else:
            self.miner_url = miner_url

        # Generate API URL (auto/manual)
        if daemon_url == '':
            try:
                with open(str(Path.home()) + "/.lotus/api", "r") as text_file:
                    daemon_api_line = text_file.read()
            except Exception  as e_generic:
                raise DaemonError(e_generic)
            daemon_api = daemon_api_line.split("/")
            daemon_api_ip = daemon_api[2]
            daemon_api_port = daemon_api[4]
            self.daemon_url = "http://" + daemon_api_ip + ":" + daemon_api_port + "/rpc/v0"
        else:
            self.daemon_url = daemon_url

        # Retrieve Token to connect miner API
        if miner_token == '':
            try:
                with open(str(Path.home()) + "/.lotusminer/token", "r") as text_file:
                    self.miner_token = text_file.read()
            except Exception  as e_generic:
                raise MinerError(e_generic)
        else:
            self.miner_token = miner_token

        # Retrieve Token to connect daemon API
        if daemon_token == '':
            try:
                with open(str(Path.home()) + "/.lotus/token", "r") as text_file:
                    self.daemon_token = text_file.read()
            except Exception  as e_generic:
                raise DaemonError(e_generic)
        else:
            self.daemon_token = daemon_token

        # RETRIEVE MINER ID
        try:
            actoraddress = self.miner_get_json("ActorAddress", [])
        except Exception as e_generic:
            raise MinerError(e_generic)
        self.miner_id = actoraddress['result']

    def daemon_get_json(self, method, params):
        """Send a request to the daemon API / This function rely on the function that support async, but present a much simpler interface"""
        try:
            result = self.daemon_get_json_multiple([[method, params]])[0]
        except Exception as e_generic:
            raise DaemonError(e_generic)
        if "error" in result.keys():
            raise DaemonError(f"\nTarget : daemon\nMethod : {method}\nParams : {params}\nResult : {result}")
        return result

    def miner_get_json(self, method, params):
        """Send a request to the miner API / This function rely on the function that support async, but present a much simpler interface"""
        try:
            result = self.miner_get_json_multiple([[method, params]])[0]
        except Exception as e_generic:
            raise MinerError(e_generic)
        if "error" in result.keys():
            raise MinerError(f"\nTarget : miner\nMethod : {method}\nParams : {params}\nResult : {result}")
        return result

    def daemon_get_json_multiple(self, requests):
        """ Send multiple request in Async mode to the daemon API"""
        try:
            results = asyncio.run(self.__get_json_multiple(self.daemon_url, self.daemon_token, requests))
        except Exception as e_generic:
            raise DaemonError(e_generic)
        return results

    def miner_get_json_multiple(self, requests):
        """ Send multiple request in Async mode to the miner API"""
        try:
            results = asyncio.run(self.__get_json_multiple(self.miner_url, self.miner_token, requests))
        except Exception as e_generic:
            raise MinerError(e_generic)
        return results

    async def __get_json(self, session, url, token, request):
        header = {'Authorization': 'Bearer ' + token}
        method = request[0]
        params = request[1]
        jsondata = {"jsonrpc": "2.0", "method": "Filecoin." + method, "params": params, "id": 3}

        try:
            async with session.post(url, json=jsondata, headers=header) as response:
                return await response.json(content_type=None)
        except Exception as e_generic:
            raise e_generic

    async def __get_json_multiple(self, url, token, requests):
        async with aiohttp.ClientSession() as session:
            tasks = []
            for request in requests:
                tasks.append(asyncio.ensure_future(self.__get_json(session, url, token, request)))
            try:
                results = await asyncio.gather(*tasks)
            except Exception as e_generic:
                raise e_generic

            return results

    def bitfield_count(self, bitfield):
        """Count bits from golang Bitfield object.

        s0nik42 reverse engineering
        https://github.com/filecoin-project/go-bitfield/blob/master/rle/rleplus.go#L88"""

        count = 0
        if len(bitfield) < 2:
            return 0
        for i in range(0, len(bitfield), 2):
            count += bitfield[i+1]
        return count

    def bitfield_to_dict(self, bitfield, state, target=None):
        """Return target enrich by the state of sectors based on a Goland Bitfield deadline"""

        target = target or {}

        # index
        sector_id = 0

        # number of bit to 1 in the bitfield (number of sectors)
        count = 0

        # If the bitfield is <2 is contains no sectors
        if len(bitfield) < 2:
            return target, count

        # parse the bitfield 2 by 2
        for i in range(0, len(bitfield), 2):
            sector_id += bitfield[i]

            # Increase the counter of the number of sectors included in the bit
            count += bitfield[i + 1]

            # for each bit set to 1 at the index
            for inc in range(0, bitfield[i + 1]):

                # Create the sector in the dictionary of not exist and set the state value to true (ex : target[SECTORID][STATE] = True // target["25"]["Active"] = true
                if str(sector_id + inc) not in target:
                    target[str(sector_id + inc)] = {}
                target[str(sector_id + inc)][state] = True

            # Increment the sector ID
            sector_id += bitfield[i + 1]
        return target, count

    def get_deadlines_enhanced(self):
        """ Merge StateMinerDeadlines StateMinerDeadlines into an unique object with the list of sectors per deadline instead of the bitfield
        Structure is :
                {
                    "Challenge": 480557,
                    "Close": 480637,
                    "CurrentEpoch": 480620,
                    "FaultCutoff": 480507,
                    "FaultDeclarationCutoff": 70,
                    "Index": 45,
                    "Open": 480577,
                    "PeriodStart": 477877,
                    "WPoStChallengeLookback": 20,
                    "WPoStChallengeWindow": 60,
                    "WPoStPeriodDeadlines": 48,
                    "WPoStProvingPeriod": 2880,
                    "deadlines": {
                        "0": {
                            "ActiveSectorsCount": 1558,
                            "AllSectorsCount": 1560,
                            "FaultySectorsCount": 0,
                            "LiveSectorsCount": 1560,
                            "PartitionsCount": 1,
                            "ProvenPartition": 0,
                            "RecoveringSectorsCount": 0,
                            "StartIn": 4110,
                            "partitions": {
                                "0": {
                                    "1": {
                                        "Active": true,
                                        "Live": true
                                    },
                                    "10": {
                                        "Active": true,
                                        "Live": true
                        [...]
            """


        # get State of each deadlines
        proven_deadlines = self.daemon_get_json("StateMinerDeadlines", [self.miner_id, self.tipset_key()])

        # Init the structures that will contains all the deadlines information
        deadlines_info = {}
        deadlines_info["cur"] = self.daemon_get_json("StateMinerProvingDeadline", [self.miner_id, self.tipset_key()])["result"]

        number_of_dls = deadlines_info["cur"]["WPoStPeriodDeadlines"]

        deadlines_info["deadlines"] = {}
        for c_dl in range(number_of_dls):
            dl_id = (deadlines_info["cur"]["Index"] + c_dl) % number_of_dls

            partitions = self.daemon_get_json("StateMinerPartitions", [self.miner_id, dl_id, self.tipset_key()])
            if partitions["result"]:
                deadlines_info["deadlines"][dl_id] = {}
                opened = deadlines_info["cur"]["Open"] + deadlines_info["cur"]["WPoStChallengeWindow"] * c_dl
                deadlines_info["deadlines"][dl_id]["StartIn"] = ((opened - deadlines_info["cur"]["CurrentEpoch"]) * 30)
                deadlines_info["deadlines"][dl_id]["FaultySectorsCount"] = 0
                deadlines_info["deadlines"][dl_id]["RecoveringSectorsCount"] = 0
                deadlines_info["deadlines"][dl_id]["ActiveSectorsCount"] = 0
                deadlines_info["deadlines"][dl_id]["LiveSectorsCount"] = 0
                deadlines_info["deadlines"][dl_id]["AllSectorsCount"] = 0
                deadlines_info["deadlines"][dl_id]["PartitionsCount"] = len(partitions["result"])
                deadlines_info["deadlines"][dl_id]["ProvenPartition"] = self.bitfield_count(proven_deadlines["result"][dl_id]["PostSubmissions"])
                deadlines_info["deadlines"][dl_id]["partitions"] = {}
                for partition_id, partition in enumerate(partitions["result"]):
                    part = {}
                    part, count = self.bitfield_to_dict(partition["FaultySectors"], "Faulty", part)
                    deadlines_info["deadlines"][dl_id]["FaultySectorsCount"] += count
                    part, count = self.bitfield_to_dict(partition["RecoveringSectors"], "Recovering", part)
                    deadlines_info["deadlines"][dl_id]["RecoveringSectorsCount"] += count
                    part, count = self.bitfield_to_dict(partition["ActiveSectors"], "Active", part)
                    deadlines_info["deadlines"][dl_id]["ActiveSectorsCount"] += count
                    part, count = self.bitfield_to_dict(partition["LiveSectors"], "Live", part)
                    deadlines_info["deadlines"][dl_id]["LiveSectorsCount"] += count

                    deadlines_info["deadlines"][dl_id]["AllSectorsCount"] += len(part.keys())
                    deadlines_info["deadlines"][dl_id]["partitions"][partition_id] = part

        return deadlines_info

    def get_deal_info_enhanced(self, deal_id):
        """ Return deald information with lookup on addresses."""
        try:
            deal_info = self.daemon_get_json("StateMarketStorageDeal", [deal_id, self.tipset_key()])["result"]
        except Exception:
            deal = {
                "Client": "unknown",
                "ClientCollateral": "unknown",
                "EndEpoch": "unknown",
                "Label": "unknown",
                "PieceCID": {
                },
                "PieceSize": "unknown",
                "Provider": "unknown",
                "ProviderCollateral": "unknown",
                "StartEpoch": "unknown",
                "StoragePricePerEpoch": "unknown",
                "VerifiedDeal": "unknown"
            }
        else:
            deal = deal_info["Proposal"]
            deal["Client"] = self.__address_lookup(deal["Client"])
            deal["Provider"] = self.__address_lookup(deal["Provider"])
        return deal

    def qa_power_for_weight(self, size, duration, deal_weight, verified_weight):
        """ Calculate the Quality adjusted power of a sector based on deals weight.
            Lotus source reference : https://github.com/filecoin-project/specs-actors/blob/8e3ed3d4e3f127577248004c841a41557a91ced2/actors/builtin/miner/policy.go#L271
        """
        if duration == 0:
            duration = 1

        quality_base_multiplier = 10
        deal_weight_multiplier = 10
        verified_deal_weight_multiplier = 100
        sector_quality_precision = 20

        sector_space_time = size * duration
        total_deal_space_time = deal_weight + verified_weight
        weighted_base_space_time = (sector_space_time - total_deal_space_time) * quality_base_multiplier
        weighted_deal_space_time = deal_weight * deal_weight_multiplier
        weighted_verified_space_time = verified_weight * verified_deal_weight_multiplier
        weighted_sum_space_time = weighted_base_space_time + weighted_deal_space_time + weighted_verified_space_time
        scaled_up_weighted_sum_space_time = weighted_sum_space_time << sector_quality_precision

        quality = (scaled_up_weighted_sum_space_time / (sector_space_time * quality_base_multiplier))
        return int(size * quality) >> sector_quality_precision

    def __get_actor_type(self, actor_code):
        try:
            a_type = multibase.decode(actor_code)[10:]
        except Exception:
            raise Exception(f'Cannot decode actor_code {actor_code}')

        if a_type in self.actor_type.keys():
            return self.actor_type[a_type]

        raise Exception(f'Unknown actor_type {a_type} derived from actor_code : {actor_code}')


    def __get_message_type(self, address, method):
        """ Return message_type of a given message.

        The code is based from an extract from : https://github.com/filecoin-project/specs-actors/blob/7d06c2806ff09868abea9e267ead2ada8438e077/actors/builtin/methods.go"""

        try:
            actor = self.daemon_get_json("StateGetActor", [address, self.tipset_key()])
        except Exception:
            return("Invalid address", "Unknown")

        code = actor["result"]["Code"]["/"]

        try:
            actor_type = self.__get_actor_type(code)
        except Exception:
            return "Unknown", "Unknown"

        try:
            message_type = self.message_type[actor_type][method-1]
        except IndexError:
            return(actor_type, "Unknown")

        return(actor_type, message_type)

    def __address_lookup(self, addr):
        """ The function lookup an address and return the corresponding name from the chain or from the know_addresses table"""

        # Check if it's an address or a name. And reallocate the data accordingly
        if addr.startswith("f0"):
            name = addr

            # Retrieve actor type
            try:
                actor = self.daemon_get_json("StateGetActor", [name, self.tipset_key()])["result"]["Code"]["/"]
            except Exception:
                return name

            # If Address is an account type
            if self.__get_actor_type(actor) == "Account":
                try:
                    addr = self.daemon_get_json("StateAccountKey", [name, self.tipset_key()])["result"]
                except Exception:
                    addr = name
            else:
                addr = name
        else:
            # Enter here if addr is really an address
            try:
                name = self.daemon_get_json("StateLookupID", [addr, self.tipset_key()])["result"]
            except Exception:
                name = addr[0:5] + "..." + addr[-5:]

        # AT THAT POINT we have a name and an adress

        # Return the name based on the following priority
        # If in the known address table
        if name in self.known_addresses:
            return self.known_addresses[name]

        if addr in self.known_addresses:
            return self.known_addresses[addr]

        return name

    def get_mpool_pending_enhanced(self, filter_from_address: list = None):
        """ Return an enhanced version of mpool pending with additionnal information : lookup on address / Method Type / etc ...

        If these information are useles, better call directly : daemon_get_json("MpoolPending",...)"""

        msg_list = []

        mpoolpending = self.daemon_get_json("MpoolPending", [self.tipset_key()])

        # Go through all messages and add informations
        for msg in mpoolpending["result"]:
            if not filter_from_address or msg["Message"]["From"] in filter_from_address:

                # Add actor_type and methode_type
                msg["Message"]["actor_type"], msg["Message"]["method_type"] = self.__get_message_type(msg["Message"]["To"], msg["Message"]["Method"])

                # Prettry print To address
                msg["Message"]["display_to"] = self.__address_lookup(msg["Message"]["To"])

                # Prettyprint From addresses
                msg["Message"]["display_from"] = self.__address_lookup(msg["Message"]["From"])

                msg_list.append(msg["Message"])

        return msg_list

    def get_local_mpool_pending_enhanced(self):
        """ Return local mpool messages """
        wallet_list = self.get_wallet_list_enhanced().keys()
        return self.get_mpool_pending_enhanced(wallet_list)

    def add_known_addresses(self, addresses: dict):
        """ Add new addresses to the vlookup database"""
        self.known_addresses.update(addresses)

    def get_chain_head(self):
        """  Update Object content with last head info"""
        chain_head = self.daemon_get_json("ChainHead", [])
        self.__chain_head = chain_head["result"]
        self.__tipset_key = chain_head["result"]["Cids"]
        self.__basefee = chain_head["result"]["Blocks"][0]["ParentBaseFee"]

    def get_storagelist_enhanced(self):
        """ Get storage list enhanced with reverse hostname lookup"""

        storage_list = self.miner_get_json("StorageList", [])

        storage_local_list = self.miner_get_json("StorageLocal", [])
        res = []
        for storage in storage_list["result"].keys():
            storage_info = self.miner_get_json("StorageInfo", [storage])

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
                storage_stat = self.miner_get_json("StorageStat", [storage])
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


    def __get_local_wallet_list(self):
        """ retrieve local wallet list, return cache version if already executed """
        if self.__local_wallet_list is None:
            self.__local_wallet_list = self.daemon_get_json("WalletList", [])["result"]
        return self.__local_wallet_list

    def get_wallet_list_enhanced(self, external_wallets=None):
        """ return wallet enrich with addresses lookp and external wallet added"""

        external_wallets = external_wallets or {}

        res = {}

        # 1 Add wallet adresses to the loop and manage the case where wallet adress doesnt exist onchain because never get any transaction
        walletlist = self.__get_local_wallet_list()
        for addr in walletlist:
            try:
                balance = self.daemon_get_json("WalletBalance", [addr])["result"]
            except Exception as e_generic:
                print(f"Warning : cannot retrieve {addr} balance : {e_generic}", file=sys.stderr)
                continue

            # Add address to the list
            res[addr] = {}
            res[addr]["balance"] = balance
            res[addr]["name"] = self.__address_lookup(addr)

            try:
                verified_result = self.daemon_get_json("StateVerifiedClientStatus", [addr, self.tipset_key()])
                res[addr]["verified_datacap"] = verified_result["result"]
            except Exception:
                res[addr]["verified_datacap"] = 0

        # 2 Add miner balance
        res[self.miner_id] = {}
        res[self.miner_id]["balance"] = self.daemon_get_json("StateMinerAvailableBalance", [self.miner_id, self.tipset_key()])["result"]
        res[self.miner_id]["name"] = self.miner_id
        res[self.miner_id]["verified_datacap"] = self.daemon_get_json("StateVerifiedClientStatus", [self.miner_id, self.tipset_key()])["result"]

        # 3 Add external_wallets :
        for addr in external_wallets:
            try:
                balance = self.daemon_get_json("WalletBalance", [addr])["result"]
            except Exception as e_generic:
                print(f"Warning : cannot retrieve {addr} balance : {e_generic}", file=sys.stderr)
                continue

            # Add address to the list
            res[addr] = {}
            res[addr]["balance"] = balance
            res[addr]["name"] = external_wallets[addr]

            try:
                verified_result = self.daemon_get_json("StateVerifiedClientStatus", [addr, self.tipset_key()])
                res[addr]["verified_datacap"] = verified_result["result"]
            except Exception:
                res[addr]["verified_datacap"] = 0

        return res

    def get_market_info_enhanced(self):
        """ create one structure with all the info related to storage and retreival market """
        res = {}

        res["storage"] = self.miner_get_json("MarketGetAsk", [])["result"]["Ask"]
        res["storage"]["ConsiderOnlineDeals"] = self.miner_get_json("DealsConsiderOnlineStorageDeals", [])["result"]
        res["storage"]["ConsiderOfflineDeals"] = self.miner_get_json("DealsConsiderOfflineStorageDeals", [])["result"]

        res["retrieval"] = self.miner_get_json("MarketGetRetrievalAsk", [])["result"]
        res["retrieval"]["ConsiderOnlineDeals"] = self.miner_get_json("DealsConsiderOnlineRetrievalDeals", [])["result"]
        res["retrieval"]["ConsiderOfflineDeals"] = self.miner_get_json("DealsConsiderOfflineRetrievalDeals", [])["result"]

        return res

    def tipset_key(self):
        """ Return  tipset_key is already retrieved or retrieve it for the chain"""
        if  self.__tipset_key is None:
            self.get_chain_head()
        return self.__tipset_key

    def chain_head(self):
        """ Return chain_head is already retrieved or retrieve it for the chain"""
        if  self.__chain_head is None:
            self.get_chain_head()
        return self.__chain_head

    def basefee(self):
        """ Return basefee is already retrieved or retrieve it for the chain"""
        if  self.__basefee is None:
            self.get_chain_head()
        return self.__basefee

class Metrics:
    """ This class manage prometheus metrics formatting / checking / print """

    # Prefix to all metrics generated by this script
    __PREFIX = "lotus_"

    # Full inventory of all metrics allowed with description  and type
    __METRICS_LIST = {
        "chain_height"                              : {"type" : "counter", "help": "return current height"},
        "chain_basefee"                             : {"type" : "gauge", "help": "return current basefee"},
        "chain_sync_diff"                           : {"type" : "gauge", "help": "return daemon sync height diff with chainhead for each daemon worker"},
        "chain_sync_status"                         : {"type" : "gauge", "help": "return daemon sync status with chainhead for each daemon worker"},
        "info"                                      : {"type" : "gauge", "help": "lotus daemon information like address version, value is set to network version number"},
        "local_time"                                : {"type" : "gauge", "help": "time on the node machine when last execution start in epoch"},
        "miner_deadline_active_partition_sector"    : {"type" : "gauge", "help": "sector belonging to the partition_id of the deadline_id"},
        "miner_deadline_active_partitions"          : {"type" : "gauge", "help": "number of partitions in the deadline"},
        "miner_deadline_active_partitions_proven"   : {"type" : "gauge", "help": "number of partitions already proven for the deadline"},
        "miner_deadline_active_sectors_active"      : {"type" : "gauge", "help": "number of active sectors"},
        "miner_deadline_active_sectors_all"         : {"type" : "gauge", "help": "number of sectors in the deadline"},
        "miner_deadline_active_sectors_faulty"      : {"type" : "gauge", "help": "number of faulty sectors"},
        "miner_deadline_active_sectors_live"        : {"type" : "gauge", "help": "number of live sectors"},
        "miner_deadline_active_sectors_recovering"  : {"type" : "gauge", "help": "number of sectors in recovering state"},
        "miner_deadline_active_start"               : {"type" : "gauge", "help": "remaining time before deadline start"},
        "miner_deadline_info"                       : {"type" : "gauge", "help": "deadlines and WPoSt informations"},
        "miner_info"                                : {"type" : "gauge", "help": "lotus miner information like address version etc"},
        "miner_info_sector_size"                    : {"type" : "gauge", "help": "lotus miner sector size"},
        "miner_market_info"                         : {"type" : "gauge", "help": "lotus miner storage and retrieval market informations"},
        "miner_netpeers_total"                      : {"type" : "gauge", "help": "return number netpeers"},
        "miner_net_protocol_in"                     : {"type" : "counter", "help": "return input net per protocol"},
        "miner_net_protocol_out"                    : {"type" : "counter", "help": "return output per protocol net"},
        "miner_net_total_in"                        : {"type" : "counter", "help": "return input net"},
        "miner_net_total_out"                       : {"type" : "counter", "help": "return output net"},
        "miner_sector_event"                        : {"type" : "gauge", "help": "contains important event of the sector life"},
        "miner_sector_sealing_deals_info"           : {"type" : "gauge", "help": "contains information related to deals that are not in Proving and Removed state."},
        "miner_sector_state"                        : {"type" : "gauge", "help": "contains current state, nb of deals, is pledged in labels"},
        "miner_sector_weight"                       : {"type" : "gauge", "help": "verified and non_verified deal spacetime weight of sector. use 'type' label to filter one"},
        "miner_sector_qa_power"                     : {"type" : "gauge", "help": "quality adjusted power of a sector based on its deals"},
        "miner_storage_available"                   : {"type" : "gauge", "help": "get storage available capacity"},
        "miner_storage_capacity"                    : {"type" : "gauge", "help": "get storage total capacity"},
        "miner_storage_info"                        : {"type" : "gauge", "help": "get storage info state"},
        "miner_storage_reserved"                    : {"type" : "gauge", "help": "get storage reserved capacity"},
        "miner_worker_cpu"                          : {"type" : "gauge", "help": "number of CPU used by lotus"},
        "miner_worker_cpu_used"                     : {"type" : "gauge", "help": "number of CPU used by lotused by lotus"},
        "miner_worker_gpu"                          : {"type" : "gauge", "help": "is the GPU used by lotus"},
        "miner_worker_gpu_used"                     : {"type" : "gauge", "help": "is the GPU used by lotus"},
        "miner_worker_id"                           : {"type" : "gauge", "help": "All lotus worker information prfer to use workername than workerid which is changing at each restart"},
        "miner_worker_job"                          : {"type" : "gauge", "help": "status of each individual job running on the workers. Value is the duration"},
        "miner_worker_mem_physical"                 : {"type" : "gauge", "help": "worker server RAM"},
        "miner_worker_mem_physical_used"            : {"type" : "gauge", "help": "worker minimal memory used"},
        "miner_worker_mem_reserved"                 : {"type" : "gauge", "help": "worker memory reserved by lotus"},
        "miner_worker_mem_swap"                     : {"type" : "gauge", "help": "server SWAP"},
        "miner_worker_mem_vmem_used"                : {"type" : "gauge", "help": "worker maximum memory used"},
        "mpool_local_message"                       : {"type" : "gauge", "help": "local message details"},
        "mpool_local_total"                         : {"type" : "gauge", "help": "return number of messages pending in local mpool"},
        "mpool_total"                               : {"type" : "gauge", "help": "return number of message pending in mpool"},
        "netpeers_total"                            : {"type" : "gauge", "help": "return number netpeers"},
        "net_protocol_in"                           : {"type" : "counter", "help": "return input net per protocol"},
        "net_protocol_out"                          : {"type" : "counter", "help": "return output per protocol net"},
        "net_total_in"                              : {"type" : "counter", "help": "return input net"},
        "net_total_out"                             : {"type" : "counter", "help": "return output net"},
        "power"                                     : {"type" : "gauge", "help": "return miner power"},
        "power_mining_eligibility"                  : {"type" : "gauge", "help": "return miner mining eligibility"},
        "scrape_duration_seconds"                   : {"type" : "gauge", "help": "execution time of the different collectors"},
        "scrape_execution_succeed"                  : {"type" : "gauge", "help": "return 1 if lotus-farcaster execution was successfully"},
        "wallet_balance"                            : {"type" : "gauge", "help": "return wallet balance"},
        "wallet_locked_balance"                     : {"type" : "gauge", "help": "return miner wallet locked funds"},
        "wallet_verified_datacap"                   : {"type" : "gauge", "help": "return miner wallet datacap per address"}
    }
    __metrics = []

    def __init__(self):
        self.local_time = int(time.time())
        self.add("local_time", value=self.local_time)

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
                print(f'# HELP {self.__PREFIX}{ m_name } { self.__METRICS_LIST[m_name]["help"] }')
                print(f'# TYPE {self.__PREFIX}{ m_name } { self.__METRICS_LIST[m_name]["type"] }')

            # Printout the formatted metric
            print(f'{self.__PREFIX}{ m_name } {{ ', end="")
            first = True
            for i in metric["labels"].keys():
                if first is True:
                    first = False
                else:
                    print(', ', end="")
                print(f'{ i }="{ metric["labels"][i] }"', end="")
            print(f' }} { metric["value"] }')
            prev = metric

    def clear(self):
        """Clear the exeisting metrics list"""
        self.__metrics = []
        self.add("local_time", value=self.local_time)

#################################################################################
# FUNCTIONS
#################################################################################
COLLECTOR_START_TIME = False
def checkpoint(collector_name):
    """Measure time for each category of calls to api and generate metrics"""
    global COLLECTOR_START_TIME
    if not COLLECTOR_START_TIME:
        COLLECTOR_START_TIME = START_TIME
    METRICS_OBJ.add("scrape_duration_seconds", value=(time.time() - COLLECTOR_START_TIME), collector=collector_name)
    COLLECTOR_START_TIME = time.time()

# REQUEST FUNCTIONS
def daemon_get(method, params):
    """wrapper for daemon api call to manage errors in a metrics environment """

    try:
        result = LOTUS_OBJ.daemon_get_json(method, params)
    except Exception as e_generic:
        terminate(e_generic)
    return result

def miner_get(method, params):
    """wrapper for miner api call to manage errors in a metrics environment """

    try:
        result = LOTUS_OBJ.miner_get_json(method, params)
    except Exception as e_generic:
        terminate(e_generic)
    return result

def daemon_get_multiple(requests):
    """wrapper for daemon api call to manage errors in a metrics environment """

    try:
        results = LOTUS_OBJ.daemon_get_json_multiple(requests)
    except Exception as e_generic:
        terminate(e_generic)
    return results

def miner_get_multiple(requests):
    """wrapper for miner api call to manage errors in a metrics environment """

    try:
        results = LOTUS_OBJ.miner_get_json_multiple(requests)
    except Exception as e_generic:
        terminate(e_generic)
    return results

def terminate(msg: str = "", value: int = 0):
    """properly terminating the process execution on error."""
    METRICS_OBJ.clear()
    METRICS_OBJ.add("scrape_execution_succeed", value=value)
    METRICS_OBJ.print_all()
    print(msg, file=sys.stderr)
    sys.exit(0)


def load_toml(toml_file):
    """ Load a tmol file into nested dict"""

    # Check if file exists
    if not os.path.exists(toml_file):
        return {}

    # Load file
    try:
        with open(toml_file) as data_file:
            nested_dict = toml.load(data_file)
    except Exception as e_generic:
        terminate(f'Error: loading file {toml_file} : {str(e_generic)}')
    else:
        return nested_dict

def main():
    """ main function """

    global START_TIME, MINER_URL, MINER_TOKEN, DAEMON_URL, DAEMON_TOKEN, LOTUS_OBJ, METRICS_OBJ

    # Start execution time mesurement
    START_TIME = time.time()

    # Create Metrics object
    METRICS_OBJ = Metrics()

    # Create Lotus object
    try:
        LOTUS_OBJ = Lotus(MINER_URL, MINER_TOKEN, DAEMON_URL, DAEMON_TOKEN)
    except DaemonError as e_generic:
        terminate(e_generic, -1)
    except MinerError as e_generic:
        terminate(e_generic, -2)

    # miner_id
    miner_id = LOTUS_OBJ.miner_id

    # Load config file to retrieve external wallet and vlookup
    addresses_config = load_toml(f"{str(Path.home())}/.lotus-exporter-farcaster/addresses.toml")

    # Add KNOWN_ADDRESSES to Lotus OBJ
    if "known_addresses" in addresses_config.keys():
        LOTUS_OBJ.add_known_addresses(addresses_config["known_addresses"])

    METRICS_OBJ.add("chain_basefee", value=LOTUS_OBJ.basefee(), miner_id=miner_id)

    # CHAIN HEIGHT
    METRICS_OBJ.add("chain_height", value=LOTUS_OBJ.chain_head()["Height"], miner_id=miner_id)
    checkpoint("ChainHead")

    # GENERATE CHAIN SYNC STATUS
    sync_status = daemon_get("SyncState", [])
    for worker in sync_status["result"]["ActiveSyncs"]:
        try:
            diff_height = worker["Target"]["Height"] - worker["Base"]["Height"]
        except Exception:
            diff_height = -1
        METRICS_OBJ.add("chain_sync_diff", value=diff_height, miner_id=miner_id, worker_id=sync_status["result"]["ActiveSyncs"].index(worker))
        METRICS_OBJ.add("chain_sync_status", value=worker["Stage"], miner_id=miner_id, worker_id=sync_status["result"]["ActiveSyncs"].index(worker))
    checkpoint("ChainSync")

    # GENERATE MINER INFO
    miner_version = miner_get("Version", [])
    checkpoint("Miner")

    # RETRIEVE MAIN ADDRESSES
    daemon_stats = daemon_get("StateMinerInfo", [LOTUS_OBJ.miner_id, LOTUS_OBJ.tipset_key()])
    miner_owner = daemon_stats["result"]["Owner"]
    miner_owner_addr = daemon_get("StateAccountKey", [miner_owner, LOTUS_OBJ.tipset_key()])["result"]
    miner_worker = daemon_stats["result"]["Worker"]
    miner_worker_addr = daemon_get("StateAccountKey", [miner_worker, LOTUS_OBJ.tipset_key()])["result"]

    # Add miner addresses to known_addresses lookup table
    LOTUS_OBJ.add_known_addresses({miner_owner: "Local Owner", miner_owner_addr: "Local Owner", miner_worker: "Local Worker", miner_worker_addr: "Local Worker"})

    try:
        miner_control0 = daemon_stats["result"]["ControlAddresses"][0]
    except Exception as e_generic:
        miner_control0 = miner_worker
    else:
        # Add miner addresses to known_addresses lookup table
        LOTUS_OBJ.add_known_addresses({miner_control0: "Local control0"})

    miner_control0_addr = daemon_get("StateAccountKey", [miner_control0, LOTUS_OBJ.tipset_key()])["result"]

    METRICS_OBJ.add("miner_info", value=1, miner_id=miner_id, version=miner_version["result"]["Version"], owner=miner_owner, owner_addr=miner_owner_addr, worker=miner_worker, worker_addr=miner_worker_addr, control0=miner_control0, control0_addr=miner_control0_addr)
    METRICS_OBJ.add("miner_info_sector_size", value=daemon_stats["result"]["SectorSize"], miner_id=miner_id)
    checkpoint("StateMinerInfo")

    # GENERATE DAEMON INFO
    daemon_network = daemon_get("StateNetworkName", [])
    daemon_network_version = daemon_get("StateNetworkVersion", [LOTUS_OBJ.tipset_key()])
    daemon_version = daemon_get("Version", [])
    METRICS_OBJ.add("info", value=daemon_network_version["result"], miner_id=miner_id, version=daemon_version["result"]["Version"], network=daemon_network["result"])
    checkpoint("Daemon")

    # GENERATE WALLET
    if "external_wallets" in addresses_config:
        walletlist = LOTUS_OBJ.get_wallet_list_enhanced(addresses_config["external_wallets"])
    else:
        walletlist = LOTUS_OBJ.get_wallet_list_enhanced()

    for addr in walletlist.keys():
        METRICS_OBJ.add("wallet_balance", value=int(walletlist[addr]["balance"])/1000000000000000000, miner_id=miner_id, address=addr, name=walletlist[addr]["name"])
        if walletlist[addr]["verified_datacap"] is not None:
            METRICS_OBJ.add("wallet_verified_datacap", value=walletlist[addr]["verified_datacap"], miner_id=miner_id, address=addr, name=walletlist[addr]["name"])

    # Retrieve locked funds balance
    locked_funds = daemon_get("StateReadState", [LOTUS_OBJ.miner_id, LOTUS_OBJ.tipset_key()])
    for i in ["PreCommitDeposits", "LockedFunds", "FeeDebt", "InitialPledge"]:
        METRICS_OBJ.add("wallet_locked_balance", value=int(locked_funds["result"]["State"][i])/1000000000000000000, miner_id=miner_id, address=LOTUS_OBJ.miner_id, locked_type=i)
    checkpoint("Balances")

    # GENERATE POWER
    powerlist = daemon_get("StateMinerPower", [LOTUS_OBJ.miner_id, LOTUS_OBJ.tipset_key()])
    for minerpower in powerlist["result"]["MinerPower"]:
        METRICS_OBJ.add("power", value=powerlist["result"]["MinerPower"][minerpower], miner_id=miner_id, scope="miner", power_type=minerpower)
    for totalpower in powerlist["result"]["TotalPower"]:
        METRICS_OBJ.add("power", value=powerlist["result"]["TotalPower"][totalpower], miner_id=miner_id, scope="network", power_type=totalpower)

    # Mining eligibility
    base_info = daemon_get("MinerGetBaseInfo", [LOTUS_OBJ.miner_id, LOTUS_OBJ.chain_head()["Height"], LOTUS_OBJ.tipset_key()])

    if base_info["result"] is None:
        print(f'ERROR MinerGetBaseInfo return no result', file=sys.stderr)
        print(f'KNOWN_REASON your miner needs to have a power >0 for Farcaster to work. Its linked to a Lotus API bug)', file=sys.stderr)
        print(f'SOLUTION restart your miner and node', file=sys.stderr)
        METRICS_OBJ.add("scrape_execution_succeed", value=0)
        sys.exit(0)

    if base_info["result"]["EligibleForMining"]:
        eligibility = 1
    else:
        eligibility = 0
    METRICS_OBJ.add("power_mining_eligibility", value=eligibility, miner_id=miner_id)
    checkpoint("Power")

    # GENERATE MPOOL
    mpool_total = len(daemon_get("MpoolPending", [LOTUS_OBJ.tipset_key()])["result"])
    local_mpool = LOTUS_OBJ.get_local_mpool_pending_enhanced()
    local_mpool_total = len(local_mpool)

    METRICS_OBJ.add("mpool_total", value=mpool_total, miner_id=miner_id)
    METRICS_OBJ.add("mpool_local_total", value=local_mpool_total, miner_id=miner_id)

    for msg in local_mpool:
        METRICS_OBJ.add("mpool_local_message", value=1, miner_id=miner_id, msg_from=msg["display_from"], msg_to=msg["display_to"], msg_nonce=msg["Nonce"], msg_value=msg["Value"], msg_gaslimit=msg["GasLimit"], msg_gasfeecap=msg["GasFeeCap"], msg_gaspremium=msg["GasPremium"], msg_method=msg["Method"], msg_method_type=msg["method_type"], msg_to_actor_type=msg["actor_type"])
    checkpoint("MPool")

    # GENERATE NET_PEERS
    daemon_netpeers = daemon_get("NetPeers", [])
    METRICS_OBJ.add("netpeers_total", value=len(daemon_netpeers["result"]), miner_id=miner_id)

    miner_netpeers = miner_get("NetPeers", [])
    METRICS_OBJ.add("miner_netpeers_total", value=len(miner_netpeers["result"]), miner_id=miner_id)
    checkpoint("NetPeers")

    # GENERATE NETSTATS XXX Verfier la qualité des stats ... lotus net, API et Grafana sont tous differents
    protocols_list = daemon_get("NetBandwidthStatsByProtocol", [])
    for protocol in protocols_list["result"]:
        METRICS_OBJ.add("net_protocol_in", value=protocols_list["result"][protocol]["TotalIn"], miner_id=miner_id, protocol=protocol)
        METRICS_OBJ.add("net_protocol_out", value=protocols_list["result"][protocol]["TotalOut"], miner_id=miner_id, protocol=protocol)

    protocols_list = miner_get("NetBandwidthStatsByProtocol", [])
    for protocol in protocols_list["result"]:
        METRICS_OBJ.add("miner_net_protocol_in", value=protocols_list["result"][protocol]["TotalIn"], miner_id=miner_id, protocol=protocol)
        METRICS_OBJ.add("miner_net_protocol_out", value=protocols_list["result"][protocol]["TotalOut"], miner_id=miner_id, protocol=protocol)

    net_list = daemon_get("NetBandwidthStats", [])
    METRICS_OBJ.add("net_total_in", value=net_list["result"]["TotalIn"], miner_id=miner_id)
    METRICS_OBJ.add("net_total_out", value=net_list["result"]["TotalOut"], miner_id=miner_id)

    net_list = miner_get("NetBandwidthStats", [])
    METRICS_OBJ.add("miner_net_total_in", value=net_list["result"]["TotalIn"], miner_id=miner_id)
    METRICS_OBJ.add("miner_net_total_out", value=net_list["result"]["TotalOut"], miner_id=miner_id)
    checkpoint("NetBandwidth")

    # GENERATE WORKER INFOS
    workerstats = miner_get("WorkerStats", [])
    # XXX 1.2.1 introduce a new worker_id format. Later we should delete it, its a useless info.
    #print("# HELP lotus_miner_worker_id All lotus worker information prfer to use workername than workerid which is changing at each restart")
    #print("# TYPE lotus_miner_worker_id gauge")
    worker_list = {}
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

        # TEST to avoid duplicate entries incase 2 workers on the same machine. This could be remove once PL will include URL in WorkerStats API call
        if worker_host not in worker_list.keys():
            worker_list[worker_host] = 1

            METRICS_OBJ.add("miner_worker_cpu", value=cpus, miner_id=miner_id, worker_host=worker_host)
            METRICS_OBJ.add("miner_worker_gpu", value=gpus, miner_id=miner_id, worker_host=worker_host)
            METRICS_OBJ.add("miner_worker_mem_physical", value=mem_physical, miner_id=miner_id, worker_host=worker_host)
            METRICS_OBJ.add("miner_worker_mem_swap", value=mem_swap, miner_id=miner_id, worker_host=worker_host)
            METRICS_OBJ.add("miner_worker_mem_physical_used", value=mem_used_min, miner_id=miner_id, worker_host=worker_host)
            METRICS_OBJ.add("miner_worker_mem_vmem_used", value=mem_used_max, miner_id=miner_id, worker_host=worker_host)
            METRICS_OBJ.add("miner_worker_mem_reserved", value=mem_reserved, miner_id=miner_id, worker_host=worker_host)
            METRICS_OBJ.add("miner_worker_gpu_used", value=gpu_used, miner_id=miner_id, worker_host=worker_host)
            METRICS_OBJ.add("miner_worker_cpu_used", value=cpu_used, miner_id=miner_id, worker_host=worker_host)
    checkpoint("Workers")

    # GENERATE JOB INFOS
    workerjobs = miner_get("WorkerJobs", [])
    for (wrk, job_list) in workerjobs["result"].items():
        for job in job_list:
            job_id = job['ID']['ID']
            sector = str(job['Sector']['Number'])

            try:
                worker_host = workerstats["result"][wrk]["Info"]["Hostname"]
            except Exception as e_generic:
                # sometime WorkerJobs return invalid worker_id like 0000-000000-0000... in that case return unknown
                worker_host = "unknown"
            task = str(job['Task'])
            job_start_time = str(job['Start'])
            run_wait = str(job['RunWait'])
            job_start_epoch = time.mktime(time.strptime(job_start_time[:19], '%Y-%m-%dT%H:%M:%S'))
            METRICS_OBJ.add("miner_worker_job", value=(START_TIME - job_start_epoch), miner_id=miner_id, job_id=job_id, worker_host=worker_host, task=task, sector_id=sector, job_start_time=job_start_time, run_wait=run_wait)
    checkpoint("Jobs")

    # GENERATE JOB SCHEDDIAG
    scheddiag = miner_get("SealingSchedDiag", [True])

    if scheddiag["result"]["SchedInfo"]["Requests"]:
        for req in scheddiag["result"]["SchedInfo"]["Requests"]:
            sector = req["Sector"]["Number"]
            task = req["TaskType"]
            METRICS_OBJ.add("miner_worker_job", miner_id=miner_id, job_id="", worker="", task=task, sector_id=sector, start="", run_wait="99")
    checkpoint("SchedDiag")

    # GENERATE SECTORS
    sector_list = miner_get("SectorsList", [])

    # remove duplicate sector ID (lotus bug)
    unique_sector_list = set(sector_list["result"])

    size = int(daemon_stats["result"]["SectorSize"])

    # Sector list will be retrieved in ASYNC mode for performance reason (x5 faster)
    # We build the list of requests we want to batch together
    # We want to retrieve all sectors details + OnChain information
    request_list = []
    for sector in unique_sector_list:
        request_list.append(["SectorsStatus", [sector, True]])
    # We execute the batch
    details = miner_get_multiple(request_list)

    # We go though all sectors and enhanced them
    for i, sector in enumerate(unique_sector_list):
        detail = details[i]
        deals = len(detail["result"]["Deals"])-detail["result"]["Deals"].count(0)
        verified_weight = 0
        deal_weight = 0
        qa_power = size

        if deals > 0 and detail["result"]["State"] != "Removed":
            duration = int(detail["result"]["Expiration"]) - int(detail["result"]["Activation"])
            verified_weight = int(detail["result"]["VerifiedDealWeight"])
            deal_weight = int(detail["result"]["DealWeight"])
            qa_power = LOTUS_OBJ.qa_power_for_weight(size, duration, deal_weight, verified_weight)

        creation_date = detail["result"]["Log"][0]["Timestamp"]
        packed_date = ""
        finalized_date = ""

        for log in range(len(detail["result"]["Log"])):
            if detail["result"]["Log"][log]["Kind"] == "event;sealing.SectorPacked":
                packed_date = detail["result"]["Log"][log]["Timestamp"]
            if detail["result"]["Log"][log]["Kind"] == "event;sealing.SectorFinalized":
                finalized_date = detail["result"]["Log"][log]["Timestamp"]
        if detail["result"]["Log"][0]["Kind"] == "event;sealing.SectorStartCC":
            pledged = 1
        else:
            pledged = 0
        METRICS_OBJ.add("miner_sector_state", value=1, miner_id=miner_id, sector_id=sector, state=detail["result"]["State"], pledged=pledged, deals=deals)
        METRICS_OBJ.add("miner_sector_weight", value=verified_weight, weight_type="verified", miner_id=miner_id, sector_id=sector)
        METRICS_OBJ.add("miner_sector_weight", value=deal_weight, weight_type="non_verified", miner_id=miner_id, sector_id=sector)
        METRICS_OBJ.add("miner_sector_qa_power", value=qa_power, miner_id=miner_id, sector_id=sector)

        if packed_date != "":
            METRICS_OBJ.add("miner_sector_event", value=packed_date, miner_id=miner_id, sector_id=sector, event_type="packed")
        if creation_date != "":
            METRICS_OBJ.add("miner_sector_event", value=creation_date, miner_id=miner_id, sector_id=sector, event_type="creation")
        if finalized_date != "":
            METRICS_OBJ.add("miner_sector_event", value=finalized_date, miner_id=miner_id, sector_id=sector, event_type="finalized")

        if detail["result"]["State"] not in ["Proving", "Removed"]:
            for deal in detail["result"]["Deals"]:
                if deal != 0:
                    deal_info = LOTUS_OBJ.get_deal_info_enhanced(deal)
                    deal_is_verified = deal_info["VerifiedDeal"]
                    deal_size = deal_info["PieceSize"]
                    deal_price_per_epoch = deal_info["StoragePricePerEpoch"]
                    deal_provider_collateral = deal_info["ProviderCollateral"]
                    deal_client_collateral = deal_info["ClientCollateral"]
                    deal_start_epoch = deal_info["StartEpoch"]
                    deal_end_epoch = deal_info["EndEpoch"]
                    deal_client = deal_info["Client"]

                    METRICS_OBJ.add("miner_sector_sealing_deals_info", value=1, miner_id=miner_id, sector_id=sector, deal_id=deal, deal_is_verified=deal_is_verified, deal_price_per_epoch=deal_price_per_epoch, deal_provider_collateral=deal_provider_collateral, deal_client_collateral=deal_client_collateral, deal_size=deal_size, deal_start_epoch=deal_start_epoch, deal_end_epoch=deal_end_epoch, deal_client=deal_client)

    checkpoint("Sectors")

    # GENERATE DEADLINES
    deadlines = LOTUS_OBJ.get_deadlines_enhanced()
    METRICS_OBJ.add("miner_deadline_info", value=1, miner_id=miner_id, current_idx=deadlines["cur"]["Index"], current_epoch=deadlines["cur"]["CurrentEpoch"], current_open_epoch=deadlines["cur"]["Open"], wpost_period_deadlines=deadlines["cur"]["WPoStPeriodDeadlines"], wpost_challenge_window=deadlines["cur"]["WPoStChallengeWindow"])
    for dl_id, deadline in deadlines["deadlines"].items():
        METRICS_OBJ.add("miner_deadline_active_start", value=deadline["StartIn"], miner_id=miner_id, index=dl_id)
        METRICS_OBJ.add("miner_deadline_active_partitions_proven", value=deadline["ProvenPartition"], miner_id=miner_id, index=dl_id)
        METRICS_OBJ.add("miner_deadline_active_partitions", value=deadline["PartitionsCount"], miner_id=miner_id, index=dl_id)
        METRICS_OBJ.add("miner_deadline_active_sectors_all", value=deadline["AllSectorsCount"], miner_id=miner_id, index=dl_id)
        METRICS_OBJ.add("miner_deadline_active_sectors_recovering", value=deadline["RecoveringSectorsCount"], miner_id=miner_id, index=dl_id)
        METRICS_OBJ.add("miner_deadline_active_sectors_faulty", value=deadline["FaultySectorsCount"], miner_id=miner_id, index=dl_id)
        METRICS_OBJ.add("miner_deadline_active_sectors_active", value=deadline["ActiveSectorsCount"], miner_id=miner_id, index=dl_id)
        METRICS_OBJ.add("miner_deadline_active_sectors_live", value=deadline["LiveSectorsCount"], miner_id=miner_id, index=dl_id)
        for partition_id, partition in deadline["partitions"].items():
            for sector_id in partition.keys():
                is_active = "Active" in partition[sector_id]
                is_live = "Live" in partition[sector_id]
                is_recovering = "Recovering" in partition[sector_id]
                is_faulty = "Faulty" in partition[sector_id]
                METRICS_OBJ.add("miner_deadline_active_partition_sector", is_active=is_active, is_live=is_live, is_recovering=is_recovering, is_faulty=is_faulty, value=1, miner_id=miner_id, deadline_id=dl_id, partition_id=partition_id, sector_id=sector_id)
    checkpoint("Deadlines")


    # GENERATE STORAGE INFO
    for sto in LOTUS_OBJ.get_storagelist_enhanced():
        METRICS_OBJ.add("miner_storage_info", value=1, miner_id=miner_id, storage_id=sto["storage_id"], storage_url=sto["url"], storage_host_name=sto["host_name"], storage_host_ip=sto["host_ip"], storage_host_port=sto["host_port"], weight=sto["weight"], can_seal=sto["can_seal"], can_store=sto["can_store"], path=sto["path"])
        METRICS_OBJ.add("miner_storage_capacity", value=sto["capacity"], miner_id=miner_id, storage_id=sto["storage_id"])
        METRICS_OBJ.add("miner_storage_available", value=sto["available"], miner_id=miner_id, storage_id=sto["storage_id"])
        METRICS_OBJ.add("miner_storage_reserved", value=sto["reserved"], miner_id=miner_id, storage_id=sto["storage_id"])
    checkpoint("Storage")

    # GENERATE MARKET INFO
    market_info = LOTUS_OBJ.get_market_info_enhanced()
    METRICS_OBJ.add("miner_market_info", value=1,
                    miner_id=miner_id,
                    retrieval_consider_online_deals=market_info["retrieval"]["ConsiderOnlineDeals"],
                    retrieval_consider_offline_deals=market_info["retrieval"]["ConsiderOfflineDeals"],
                    retrieval_price_per_byte=market_info["retrieval"]["PricePerByte"],
                    retrieval_unseal_price=market_info["retrieval"]["UnsealPrice"],
                    storage_consider_online_deals=market_info["storage"]["ConsiderOnlineDeals"],
                    storage_consider_offline_deals=market_info["storage"]["ConsiderOfflineDeals"],
                    storage_expiry=market_info["storage"]["Expiry"],
                    storage_max_piece_size=market_info["storage"]["MaxPieceSize"],
                    storage_min_piece_size=market_info["storage"]["MinPieceSize"],
                    storage_unverified_price=market_info["storage"]["Price"],
                    storage_verified_price=market_info["storage"]["VerifiedPrice"],
                    )
    checkpoint("Market")

    # GENERATE DEALS INFOS
    # XXX NOT FINISHED
    # publish_deals = miner_get("MarketPendingDeals", '[]'):
    # METRICS_OBJ.add("miner_pending_deals", value=1, miner_id=miner_id, deal_id=deal, deal_is_verified=deal_is_verified, deal_price_per_epoch=deal_price_per_epoch, deal_provider_collateral=deal_provider_collateral, deal_client_collateral=deal_client_collateral, deal_size=deal_size, deal_start_epoch=deal_start_epoch, deal_end_epoch=deal_end_epoch, deal_client=deal_client)
    # checkpoint("Deals")

    # Execution successfully finished, printout all data for prometheus
    # GENERATE SCRAPE TIME
    METRICS_OBJ.add("scrape_duration_seconds", value=(time.time() - START_TIME), collector="All")
    METRICS_OBJ.add("scrape_execution_succeed", value=1)
    METRICS_OBJ.print_all()

    # XXX TODO
    # Bugs :
    #   Gerer le bug lier à l'absence de Worker (champs GPU vide, etc...)
    # Retrieval Market :
    #   GENERATE RETRIEVAL MARKET
    #   print(miner_get("MarketListRetrievalDeals",[]))
    #   GENERATE DATA TRANSFERS
    #   print(miner_get("MarketListDataTransfers",[]))
    #   Pending Deals
    #   MarketPendingDeals
    # Deals : MarketListIncompleteDeals
    # Others :
    #   A quoi correcpond le champs retry dans le SectorStatus
    #   rajouter les errors de sectors
    #   print(daemon_get("StateMinerFaults",[miner_id,LOTUS_OBJ.tipset_key()]))
    # Add Partition to Deadlines

if __name__ == "__main__":

    # Declare Global Variables
    START_TIME = None
    LOTUS_OBJ = None
    METRICS_OBJ = None

    # execute only if run as a script
    main()
