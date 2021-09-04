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
from contextlib import contextmanager
import json
import time
import sys
import socket
import os
import asyncio
import aiohttp
import toml
import multibase
import argparse
import logging
from functools import wraps

VERSION = "v2.0.3"

#################################################################################
# CLASS DEFINITION
#################################################################################

class Error(Exception):
    """Exception from this module"""

    @classmethod
    def wrap(cls, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except cls:
                # Don't wrap already wrapped exceptions
                raise
            except Exception as exc:
                raise DaemonError from exc
        return wrapper

class MinerError(Error):
    """Customer Exception to identify error coming from the miner. Used  for the dashboard Status panel"""

class DaemonError(Error):
    """Customer Exception to identify error coming from the miner. Used  for the dashboard Status panel"""

class Lotus(object):
    """This class manages all interaction with lotus API miner and daemon"""

    def __init__(self, miner_url, miner_token, daemon_url, daemon_token):
        self.daemon = Daemon(daemon_url, daemon_token)
        self.miner = Miner(miner_url, miner_token)

        # RETRIEVE MINER ID
        actoraddress = self.miner.get_json("ActorAddress", [])
        self.miner_id = actoraddress['result']

    def get_deadlines_enhanced(self):
        return self.daemon.get_deadlines_enhanced(self.miner_id)

    def get_deal_info_enhanced(self, deal_id):
        return self.daemon.get_deal_info_enhanced(deal_id)

    @staticmethod
    def qa_power_for_weight(*args, **kwargs):
        return LotusBase.qa_power_for_weight(*args, **kwargs)

    def get_local_mpool_pending_enhanced(self):
        return self.daemon.get_local_mpool_pending_enhanced(self.miner_id)

    def add_known_addresses(self, *args, **kwargs):
        return self.daemon.known_addresses().update(*args, **kwargs)

    def get_storagelist_enhanced(self):
        return self.miner.get_storagelist_enhanced()

    def get_wallet_list_enhanced(self, external_wallets=None):
        return self.daemon.get_wallet_list_enhanced(self.miner_id, external_wallets)

    def get_market_info_enhanced(self):
        return self.miner.get_market_info_enhanced()

    def tipset_key(self):
        return self.daemon.tipset_key()

    def chain_head(self):
        return self.daemon.chain_head()

    def basefee(self):
        return self.daemon.basefee()

    # REQUEST FUNCTIONS
    def daemon_get(self, *args, **kwargs):
        """wrapper for daemon api call to manage errors in a metrics environment """

        try:
            return self.daemon.get_json(*args, **kwargs)
        except Exception as e_generic:
            METRICS_OBJ.terminate(e_generic)

    def miner_get(self, *args, **kwargs):
        """wrapper for miner api call to manage errors in a metrics environment """

        try:
            return self.miner.get_json(*args, **kwargs)
        except Exception as e_generic:
            METRICS_OBJ.terminate(e_generic)

    def miner_get_multiple(self, *args, **kwargs):
        """wrapper for miner api call to manage errors in a metrics environment """

        try:
            return self.miner.get_json_multiple(*args, **kwargs)
        except Exception as e_generic:
            METRICS_OBJ.terminate(e_generic)

class LotusBase(object):
    target = "lotus"
    Error = Error

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


    def __init__(self, url, token):
        self.url = url
        self.token = token

    @Error.wrap
    def get_json(self, method, params):
        """Send a request to the daemon API / This function rely on the function that support async, but present a much simpler interface"""
        result = self.get_json_multiple([[method, params]])[0]
        if "error" in result.keys():
            raise DaemonError(f"\nTarget : {self.target}\nMethod : {method}\nParams : {params}\nResult : {result}")
        return result

    @Error.wrap
    def get_json_multiple(self, requests):
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

    @staticmethod
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

    @staticmethod
    def bitfield_to_dict(bitfield, state, target=None):
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

    @staticmethod
    def qa_power_for_weight(size, duration, deal_weight, verified_weight):
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

    @classmethod
    def _get_actor_type(cls, actor_code):
        try:
            a_type = multibase.decode(actor_code)[10:]
        except Exception:
            raise Exception(f'Cannot decode actor_code {actor_code}')

        if a_type in cls.actor_type.keys():
            return cls.actor_type[a_type]

        raise Exception(f'Unknown actor_type {a_type} derived from actor_code : {actor_code}')




class Daemon(LotusBase):
    target = "daemon"
    Error = DaemonError

    def chain_head(self):
        """ Return chain_head is already retrieved or retrieve it for the chain"""
        try:
            return self.__chain_head
        except AttributeError:
            self.__chain_head = self.get_json("ChainHead", [])["result"]
        return self.__chain_head

    def tipset_key(self):
        """ Return  tipset_key """
        return self.chain_head()["Cids"]

    def basefee(self):
        """ Return basefee """
        return self.chain_head()["Blocks"][0]["ParentBaseFee"]

    def known_addresses(self):
        try:
            return self._known_addresses
        except AttributeError:
            self._known_addresses = {}
        return self._known_addresses

    def __address_lookup(self, addr):
        """ The function lookup an address and return the corresponding name from the chain or from the know_addresses table"""
        # Try the simplest case first, whatever we have is known
        try:
            return self.known_addresses()[addr]
        except KeyError:
            pass

        name = None
        # second character is 0, this is a short name
        if len(addr) >= 2 and addr[1] == "0":
            name, addr = addr, None
            try:
                actor = self.get_json("StateGetActor", [name, self.tipset_key()])["result"]["Code"]["/"]
                assert self._get_actor_type(actor) == "Account" # break out of the try if false
                addr = self.get_json("StateAccountKey", [addr, self.tipset_key()])["result"]
            except:
                pass

        trunc_addr = addr[:5] + "..." + addr[-5:] if addr else None
        if trunc_addr and not name:
            # maybe the truncated address is known
            name = self.known_addresses().get(trunc_addr)

        if addr and not name:
            try:
                name = self.get_json("StateLookupID", [addr, self.tipset_key()])["result"]
            except:
                pass

        # Use whatever we have at this point
        addr = addr or name
        name = name or trunc_addr

        # Save for next time
        self.known_addresses()[addr] = name
        self.known_addresses()[name] = name
        return name

    def __get_message_type(self, address, method):
        """ Return message_type of a given message.

        The code is based from an extract from : https://github.com/filecoin-project/specs-actors/blob/7d06c2806ff09868abea9e267ead2ada8438e077/actors/builtin/methods.go"""

        try:
            actor = self.get_json("StateGetActor", [address, self.tipset_key()])
        except Exception:
            return("Invalid address", "Unknown")

        code = actor["result"]["Code"]["/"]

        try:
            actor_type = self._get_actor_type(code)
        except Exception:
            return "Unknown", "Unknown"

        try:
            message_type = self.message_type[actor_type][method-1]
        except (IndexError, KeyError):
            return(actor_type, "Unknown")

        return(actor_type, message_type)

    def get_deadlines_enhanced(self, miner_id):
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
        proven_deadlines = self.get_json("StateMinerDeadlines", [miner_id, self.tipset_key()])

        # Init the structures that will contains all the deadlines information
        deadlines_info = {}
        deadlines_info["cur"] = self.get_json("StateMinerProvingDeadline", [miner_id, self.tipset_key()])["result"]

        number_of_dls = deadlines_info["cur"]["WPoStPeriodDeadlines"]

        deadlines_info["deadlines"] = {}
        for c_dl in range(number_of_dls):
            dl_id = (deadlines_info["cur"]["Index"] + c_dl) % number_of_dls

            partitions = self.get_json("StateMinerPartitions", [miner_id, dl_id, self.tipset_key()])
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
            deal_info = self.get_json("StateMarketStorageDeal", [deal_id, self.tipset_key()])["result"]
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

    def get_mpool_pending_enhanced(self, filter_from_address: list = None):
        """ Return an enhanced version of mpool pending with additionnal information : lookup on address / Method Type / etc ...

        If these information are useles, better call directly : daemon_get_json("MpoolPending",...)"""

        msg_list = []

        mpoolpending = self.get_json("MpoolPending", [self.tipset_key()])

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

    def __get_local_wallet_list(self):
        """ retrieve local wallet list, return cache version if already executed """
        try:
            return self.__local_wallet_list
        except AttributeError:
            self.__local_wallet_list = self.get_json("WalletList", [])["result"]
        return self.__local_wallet_list

    def get_wallet_list_enhanced(self, miner_id, external_wallets=None):
        """ return wallet enrich with addresses lookp and external wallet added"""

        external_wallets = external_wallets or {}

        res = {}

        # 1 Add wallet adresses to the loop and manage the case where wallet adress doesnt exist onchain because never get any transaction
        walletlist = self.__get_local_wallet_list()
        for addr in walletlist:
            try:
                balance = self.get_json("WalletBalance", [addr])["result"]
            except Exception as e_generic:
                logging.warn(f"cannot retrieve {addr} balance : {e_generic}")
                continue

            # Add address to the list
            res[addr] = {}
            res[addr]["balance"] = balance
            res[addr]["name"] = self.__address_lookup(addr)

            try:
                verified_result = self.get_json("StateVerifiedClientStatus", [addr, self.tipset_key()])
                res[addr]["verified_datacap"] = verified_result["result"]
            except Exception:
                res[addr]["verified_datacap"] = 0

        # 2 Add miner balance
        res[miner_id] = {}
        res[miner_id]["balance"] = self.get_json("StateMinerAvailableBalance", [miner_id, self.tipset_key()])["result"]
        res[miner_id]["name"] = miner_id
        res[miner_id]["verified_datacap"] = self.get_json("StateVerifiedClientStatus", [miner_id, self.tipset_key()])["result"]

        # 3 Add external_wallets :
        for addr in external_wallets:
            try:
                balance = self.get_json("WalletBalance", [addr])["result"]
            except Exception as e_generic:
                logging.warn(f"cannot retrieve {addr} balance : {e_generic}")
                continue

            # Add address to the list
            res[addr] = {}
            res[addr]["balance"] = balance
            res[addr]["name"] = external_wallets[addr]

            try:
                verified_result = self.get_json("StateVerifiedClientStatus", [addr, self.tipset_key()])
                res[addr]["verified_datacap"] = verified_result["result"]
            except Exception:
                res[addr]["verified_datacap"] = 0

        return res

    def get_local_mpool_pending_enhanced(self, miner_id):
        """ Return local mpool messages """
        wallet_list = self.get_wallet_list_enhanced(miner_id).keys()
        return self.get_mpool_pending_enhanced(wallet_list)

class Miner(LotusBase):
    target = "miner"
    Error = MinerError

    def get_market_info_enhanced(self):
        """ create one structure with all the info related to storage and retreival market """
        res = {}

        res["storage"] = self.get_json("MarketGetAsk", [])["result"]["Ask"]
        res["storage"]["ConsiderOnlineDeals"] = self.get_json("DealsConsiderOnlineStorageDeals", [])["result"]
        res["storage"]["ConsiderOfflineDeals"] = self.get_json("DealsConsiderOfflineStorageDeals", [])["result"]

        res["retrieval"] = self.get_json("MarketGetRetrievalAsk", [])["result"]
        res["retrieval"]["ConsiderOnlineDeals"] = self.get_json("DealsConsiderOnlineRetrievalDeals", [])["result"]
        res["retrieval"]["ConsiderOfflineDeals"] = self.get_json("DealsConsiderOfflineRetrievalDeals", [])["result"]

        return res

    def get_storagelist_enhanced(self):
        """ Get storage list enhanced with reverse hostname lookup"""

        storage_list = self.get_json("StorageList", [])

        storage_local_list = self.get_json("StorageLocal", [])
        res = []
        for storage in storage_list["result"].keys():
            storage_info = self.get_json("StorageInfo", [storage])

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
                storage_stat = self.get_json("StorageStat", [storage])
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
        self._printed_metrics = set()

    def __enter__(self):
        self._start_time = time.time()
        self.print("local_time", value=int(self._start_time))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        succeeded = exc_val is None
        self.print("scrape_duration_seconds", value=(time.time() - self._start_time), collector="All")
        self.print("scrape_execution_succeed", value=int(succeeded))

    def print(self, metric: str = "", value: float = 1, **labels):
        """ add a new metrics """

        # Check if metric is in the list of the metrics allowed
        if metric not in self.__METRICS_LIST:
            raise Exception(f'metric "{metric}" undefined in __METRICS_LIST')

        # Check if a the HELP and TYPE has already been displayed written
        if metric not in self._printed_metrics:
            print(f'# HELP {self.__PREFIX}{ metric } { self.__METRICS_LIST[metric]["help"] }')
            print(f'# TYPE {self.__PREFIX}{ metric } { self.__METRICS_LIST[metric]["type"] }')
            self._printed_metrics.add(metric)

        # Printout the formatted metric
        labels_txt = ", ".join(f'{ l }="{ v }"' for l, v in labels.items())
        print(f'{self.__PREFIX}{ metric } {{ { labels_txt } }} { value }')

    @contextmanager
    # Create a new collector context that will record the scrape duration for this category of metrics
    def collector(self, collector_name):
        start_time = time.time()
        succeeded = True
        try:
            yield self
        except:
            succeeded = False
        finally:
            self.print("scrape_duration_seconds", value=(time.time() - start_time), collector=collector_name)
            self.print("scrape_execution_succeed", value=int(succeeded), collector=collector_name)

    COLLECTOR_START_TIME = False
    def checkpoint(self, collector_name):
        """Measure time for each category of calls to api and generate metrics"""
        if not self.COLLECTOR_START_TIME:
            self.COLLECTOR_START_TIME = START_TIME
        self.print("scrape_duration_seconds", value=(time.time() - self.COLLECTOR_START_TIME), collector=collector_name)
        self.COLLECTOR_START_TIME = time.time()

    def terminate(self, msg: str = "", value: int = 0):
        """properly terminating the process execution on error."""
        self.print("scrape_execution_succeed", value=value)
        print(msg, file=sys.stderr)
        sys.exit(0)


#################################################################################
# FUNCTIONS
#################################################################################

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
        METRICS_OBJ.terminate(f'Error: loading file {toml_file} : {str(e_generic)}')
    else:
        return nested_dict

def run(lotus, metrics, addresses_config):
    """ run metrics collection and export """

    global START_TIME

    # miner_id
    miner_id = lotus.miner_id

    # Add KNOWN_ADDRESSES to Lotus OBJ
    if "known_addresses" in addresses_config.keys():
        lotus.add_known_addresses(addresses_config["known_addresses"])

    metrics.print("chain_basefee", value=lotus.basefee(), miner_id=miner_id)

    # CHAIN HEIGHT
    metrics.print("chain_height", value=lotus.chain_head()["Height"], miner_id=miner_id)
    metrics.checkpoint("ChainHead")

    # GENERATE CHAIN SYNC STATUS
    sync_status = lotus.daemon_get("SyncState", [])
    for worker in sync_status["result"]["ActiveSyncs"]:
        try:
            diff_height = worker["Target"]["Height"] - worker["Base"]["Height"]
        except Exception:
            diff_height = -1
        metrics.print("chain_sync_diff", value=diff_height, miner_id=miner_id, worker_id=sync_status["result"]["ActiveSyncs"].index(worker))
        metrics.print("chain_sync_status", value=worker["Stage"], miner_id=miner_id, worker_id=sync_status["result"]["ActiveSyncs"].index(worker))
    metrics.checkpoint("ChainSync")

    # GENERATE MINER INFO
    miner_version = lotus.miner_get("Version", [])
    metrics.checkpoint("Miner")

    # RETRIEVE MAIN ADDRESSES
    daemon_stats = lotus.daemon_get("StateMinerInfo", [lotus.miner_id, lotus.tipset_key()])
    miner_owner = daemon_stats["result"]["Owner"]
    miner_owner_addr = lotus.daemon_get("StateAccountKey", [miner_owner, lotus.tipset_key()])["result"]
    miner_worker = daemon_stats["result"]["Worker"]
    miner_worker_addr = lotus.daemon_get("StateAccountKey", [miner_worker, lotus.tipset_key()])["result"]

    # Add miner addresses to known_addresses lookup table
    lotus.add_known_addresses({miner_owner: "Local Owner", miner_owner_addr: "Local Owner", miner_worker: "Local Worker", miner_worker_addr: "Local Worker"})

    try:
        miner_control0 = daemon_stats["result"]["ControlAddresses"][0]
    except Exception as e_generic:
        miner_control0 = miner_worker
    else:
        # Add miner addresses to known_addresses lookup table
        lotus.add_known_addresses({miner_control0: "Local control0"})

    miner_control0_addr = lotus.daemon_get("StateAccountKey", [miner_control0, lotus.tipset_key()])["result"]

    metrics.print("miner_info", value=1, miner_id=miner_id, version=miner_version["result"]["Version"], owner=miner_owner, owner_addr=miner_owner_addr, worker=miner_worker, worker_addr=miner_worker_addr, control0=miner_control0, control0_addr=miner_control0_addr)
    metrics.print("miner_info_sector_size", value=daemon_stats["result"]["SectorSize"], miner_id=miner_id)
    metrics.checkpoint("StateMinerInfo")

    # GENERATE DAEMON INFO
    daemon_network = lotus.daemon_get("StateNetworkName", [])
    daemon_network_version = lotus.daemon_get("StateNetworkVersion", [lotus.tipset_key()])
    daemon_version = lotus.daemon_get("Version", [])
    metrics.print("info", value=daemon_network_version["result"], miner_id=miner_id, version=daemon_version["result"]["Version"], network=daemon_network["result"])
    metrics.checkpoint("Daemon")

    # GENERATE WALLET
    if "external_wallets" in addresses_config:
        walletlist = lotus.get_wallet_list_enhanced(addresses_config["external_wallets"])
    else:
        walletlist = lotus.get_wallet_list_enhanced()

    for addr in walletlist.keys():
        metrics.print("wallet_balance", value=int(walletlist[addr]["balance"])/1000000000000000000, miner_id=miner_id, address=addr, name=walletlist[addr]["name"])
        if walletlist[addr]["verified_datacap"] is not None:
            metrics.print("wallet_verified_datacap", value=walletlist[addr]["verified_datacap"], miner_id=miner_id, address=addr, name=walletlist[addr]["name"])

    # Retrieve locked funds balance
    locked_funds = lotus.daemon_get("StateReadState", [lotus.miner_id, lotus.tipset_key()])
    for i in ["PreCommitDeposits", "LockedFunds", "FeeDebt", "InitialPledge"]:
        metrics.print("wallet_locked_balance", value=int(locked_funds["result"]["State"][i])/1000000000000000000, miner_id=miner_id, address=lotus.miner_id, locked_type=i)
    metrics.checkpoint("Balances")

    # GENERATE POWER
    powerlist = lotus.daemon_get("StateMinerPower", [lotus.miner_id, lotus.tipset_key()])
    for minerpower in powerlist["result"]["MinerPower"]:
        metrics.print("power", value=powerlist["result"]["MinerPower"][minerpower], miner_id=miner_id, scope="miner", power_type=minerpower)
    for totalpower in powerlist["result"]["TotalPower"]:
        metrics.print("power", value=powerlist["result"]["TotalPower"][totalpower], miner_id=miner_id, scope="network", power_type=totalpower)

    # Mining eligibility
    base_info = lotus.daemon_get("MinerGetBaseInfo", [lotus.miner_id, lotus.chain_head()["Height"], lotus.tipset_key()])

    if base_info["result"] is None:
        logging.error(f'MinerGetBaseInfo returned no result')
        logging.info(f'KNOWN_REASON your miner needs to have a power >0 for Farcaster to work. Its linked to a Lotus API bug)')
        logging.info(f'SOLUTION restart your miner and node')
        metrics.print("scrape_execution_succeed", value=0)
        sys.exit(0)

    if base_info["result"]["EligibleForMining"]:
        eligibility = 1
    else:
        eligibility = 0
    metrics.print("power_mining_eligibility", value=eligibility, miner_id=miner_id)
    metrics.checkpoint("Power")

    # GENERATE MPOOL
    mpool_total = len(lotus.daemon_get("MpoolPending", [lotus.tipset_key()])["result"])
    local_mpool = lotus.get_local_mpool_pending_enhanced()
    local_mpool_total = len(local_mpool)

    metrics.print("mpool_total", value=mpool_total, miner_id=miner_id)
    metrics.print("mpool_local_total", value=local_mpool_total, miner_id=miner_id)

    for msg in local_mpool:
        metrics.print("mpool_local_message", value=1, miner_id=miner_id, msg_from=msg["display_from"], msg_to=msg["display_to"], msg_nonce=msg["Nonce"], msg_value=msg["Value"], msg_gaslimit=msg["GasLimit"], msg_gasfeecap=msg["GasFeeCap"], msg_gaspremium=msg["GasPremium"], msg_method=msg["Method"], msg_method_type=msg["method_type"], msg_to_actor_type=msg["actor_type"])
    metrics.checkpoint("MPool")

    # GENERATE NET_PEERS
    daemon_netpeers = lotus.daemon_get("NetPeers", [])
    metrics.print("netpeers_total", value=len(daemon_netpeers["result"]), miner_id=miner_id)

    miner_netpeers = lotus.miner_get("NetPeers", [])
    metrics.print("miner_netpeers_total", value=len(miner_netpeers["result"]), miner_id=miner_id)
    metrics.checkpoint("NetPeers")

    # GENERATE NETSTATS XXX Verfier la qualité des stats ... lotus net, API et Grafana sont tous differents
    protocols_list = lotus.daemon_get("NetBandwidthStatsByProtocol", [])
    for protocol in protocols_list["result"]:
        metrics.print("net_protocol_in", value=protocols_list["result"][protocol]["TotalIn"], miner_id=miner_id, protocol=protocol)
        metrics.print("net_protocol_out", value=protocols_list["result"][protocol]["TotalOut"], miner_id=miner_id, protocol=protocol)

    protocols_list = lotus.miner_get("NetBandwidthStatsByProtocol", [])
    for protocol in protocols_list["result"]:
        metrics.print("miner_net_protocol_in", value=protocols_list["result"][protocol]["TotalIn"], miner_id=miner_id, protocol=protocol)
        metrics.print("miner_net_protocol_out", value=protocols_list["result"][protocol]["TotalOut"], miner_id=miner_id, protocol=protocol)

    net_list = lotus.daemon_get("NetBandwidthStats", [])
    metrics.print("net_total_in", value=net_list["result"]["TotalIn"], miner_id=miner_id)
    metrics.print("net_total_out", value=net_list["result"]["TotalOut"], miner_id=miner_id)

    net_list = lotus.miner_get("NetBandwidthStats", [])
    metrics.print("miner_net_total_in", value=net_list["result"]["TotalIn"], miner_id=miner_id)
    metrics.print("miner_net_total_out", value=net_list["result"]["TotalOut"], miner_id=miner_id)
    metrics.checkpoint("NetBandwidth")

    # GENERATE WORKER INFOS
    workerstats = lotus.miner_get("WorkerStats", [])
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

            metrics.print("miner_worker_cpu", value=cpus, miner_id=miner_id, worker_host=worker_host)
            metrics.print("miner_worker_gpu", value=gpus, miner_id=miner_id, worker_host=worker_host)
            metrics.print("miner_worker_mem_physical", value=mem_physical, miner_id=miner_id, worker_host=worker_host)
            metrics.print("miner_worker_mem_swap", value=mem_swap, miner_id=miner_id, worker_host=worker_host)
            metrics.print("miner_worker_mem_physical_used", value=mem_used_min, miner_id=miner_id, worker_host=worker_host)
            metrics.print("miner_worker_mem_vmem_used", value=mem_used_max, miner_id=miner_id, worker_host=worker_host)
            metrics.print("miner_worker_mem_reserved", value=mem_reserved, miner_id=miner_id, worker_host=worker_host)
            metrics.print("miner_worker_gpu_used", value=gpu_used, miner_id=miner_id, worker_host=worker_host)
            metrics.print("miner_worker_cpu_used", value=cpu_used, miner_id=miner_id, worker_host=worker_host)
    metrics.checkpoint("Workers")

    # GENERATE JOB INFOS
    workerjobs = lotus.miner_get("WorkerJobs", [])
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
            metrics.print("miner_worker_job", value=(START_TIME - job_start_epoch), miner_id=miner_id, job_id=job_id, worker_host=worker_host, task=task, sector_id=sector, job_start_time=job_start_time, run_wait=run_wait)
    metrics.checkpoint("Jobs")

    # GENERATE JOB SCHEDDIAG
    scheddiag = lotus.miner_get("SealingSchedDiag", [True])

    if scheddiag["result"]["SchedInfo"]["Requests"]:
        for req in scheddiag["result"]["SchedInfo"]["Requests"]:
            sector = req["Sector"]["Number"]
            task = req["TaskType"]
            metrics.print("miner_worker_job", miner_id=miner_id, job_id="", worker="", task=task, sector_id=sector, start="", run_wait="99")
    metrics.checkpoint("SchedDiag")

    # GENERATE SECTORS
    sector_list = lotus.miner_get("SectorsList", [])

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
    details = lotus.miner_get_multiple(request_list)

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
            qa_power = lotus.qa_power_for_weight(size, duration, deal_weight, verified_weight)

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
        metrics.print("miner_sector_state", value=1, miner_id=miner_id, sector_id=sector, state=detail["result"]["State"], pledged=pledged, deals=deals)
        metrics.print("miner_sector_weight", value=verified_weight, weight_type="verified", miner_id=miner_id, sector_id=sector)
        metrics.print("miner_sector_weight", value=deal_weight, weight_type="non_verified", miner_id=miner_id, sector_id=sector)
        metrics.print("miner_sector_qa_power", value=qa_power, miner_id=miner_id, sector_id=sector)

        if packed_date != "":
            metrics.print("miner_sector_event", value=packed_date, miner_id=miner_id, sector_id=sector, event_type="packed")
        if creation_date != "":
            metrics.print("miner_sector_event", value=creation_date, miner_id=miner_id, sector_id=sector, event_type="creation")
        if finalized_date != "":
            metrics.print("miner_sector_event", value=finalized_date, miner_id=miner_id, sector_id=sector, event_type="finalized")

        if detail["result"]["State"] not in ["Proving", "Removed"]:
            for deal in detail["result"]["Deals"]:
                if deal != 0:
                    deal_info = lotus.get_deal_info_enhanced(deal)
                    deal_is_verified = deal_info["VerifiedDeal"]
                    deal_size = deal_info["PieceSize"]
                    deal_price_per_epoch = deal_info["StoragePricePerEpoch"]
                    deal_provider_collateral = deal_info["ProviderCollateral"]
                    deal_client_collateral = deal_info["ClientCollateral"]
                    deal_start_epoch = deal_info["StartEpoch"]
                    deal_end_epoch = deal_info["EndEpoch"]
                    deal_client = deal_info["Client"]

                    metrics.print("miner_sector_sealing_deals_info", value=1, miner_id=miner_id, sector_id=sector, deal_id=deal, deal_is_verified=deal_is_verified, deal_price_per_epoch=deal_price_per_epoch, deal_provider_collateral=deal_provider_collateral, deal_client_collateral=deal_client_collateral, deal_size=deal_size, deal_start_epoch=deal_start_epoch, deal_end_epoch=deal_end_epoch, deal_client=deal_client)

    metrics.checkpoint("Sectors")

    # GENERATE DEADLINES
    deadlines = lotus.get_deadlines_enhanced()
    metrics.print("miner_deadline_info", value=1, miner_id=miner_id, current_idx=deadlines["cur"]["Index"], current_epoch=deadlines["cur"]["CurrentEpoch"], current_open_epoch=deadlines["cur"]["Open"], wpost_period_deadlines=deadlines["cur"]["WPoStPeriodDeadlines"], wpost_challenge_window=deadlines["cur"]["WPoStChallengeWindow"])
    for dl_id, deadline in deadlines["deadlines"].items():
        metrics.print("miner_deadline_active_start", value=deadline["StartIn"], miner_id=miner_id, index=dl_id)
        metrics.print("miner_deadline_active_partitions_proven", value=deadline["ProvenPartition"], miner_id=miner_id, index=dl_id)
        metrics.print("miner_deadline_active_partitions", value=deadline["PartitionsCount"], miner_id=miner_id, index=dl_id)
        metrics.print("miner_deadline_active_sectors_all", value=deadline["AllSectorsCount"], miner_id=miner_id, index=dl_id)
        metrics.print("miner_deadline_active_sectors_recovering", value=deadline["RecoveringSectorsCount"], miner_id=miner_id, index=dl_id)
        metrics.print("miner_deadline_active_sectors_faulty", value=deadline["FaultySectorsCount"], miner_id=miner_id, index=dl_id)
        metrics.print("miner_deadline_active_sectors_active", value=deadline["ActiveSectorsCount"], miner_id=miner_id, index=dl_id)
        metrics.print("miner_deadline_active_sectors_live", value=deadline["LiveSectorsCount"], miner_id=miner_id, index=dl_id)
        for partition_id, partition in deadline["partitions"].items():
            for sector_id in partition.keys():
                is_active = "Active" in partition[sector_id]
                is_live = "Live" in partition[sector_id]
                is_recovering = "Recovering" in partition[sector_id]
                is_faulty = "Faulty" in partition[sector_id]
                metrics.print("miner_deadline_active_partition_sector", is_active=is_active, is_live=is_live, is_recovering=is_recovering, is_faulty=is_faulty, value=1, miner_id=miner_id, deadline_id=dl_id, partition_id=partition_id, sector_id=sector_id)
    metrics.checkpoint("Deadlines")


    # GENERATE STORAGE INFO
    for sto in lotus.get_storagelist_enhanced():
        metrics.print("miner_storage_info", value=1, miner_id=miner_id, storage_id=sto["storage_id"], storage_url=sto["url"], storage_host_name=sto["host_name"], storage_host_ip=sto["host_ip"], storage_host_port=sto["host_port"], weight=sto["weight"], can_seal=sto["can_seal"], can_store=sto["can_store"], path=sto["path"])
        metrics.print("miner_storage_capacity", value=sto["capacity"], miner_id=miner_id, storage_id=sto["storage_id"])
        metrics.print("miner_storage_available", value=sto["available"], miner_id=miner_id, storage_id=sto["storage_id"])
        metrics.print("miner_storage_reserved", value=sto["reserved"], miner_id=miner_id, storage_id=sto["storage_id"])
    metrics.checkpoint("Storage")

    # GENERATE MARKET INFO
    market_info = lotus.get_market_info_enhanced()
    metrics.print("miner_market_info", value=1,
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
    metrics.checkpoint("Market")

    # GENERATE DEALS INFOS
    # XXX NOT FINISHED
    # publish_deals = miner_get("MarketPendingDeals", '[]'):
    # METRICS_OBJ.add("miner_pending_deals", value=1, miner_id=miner_id, deal_id=deal, deal_is_verified=deal_is_verified, deal_price_per_epoch=deal_price_per_epoch, deal_provider_collateral=deal_provider_collateral, deal_client_collateral=deal_client_collateral, deal_size=deal_size, deal_start_epoch=deal_start_epoch, deal_end_epoch=deal_end_epoch, deal_client=deal_client)
    # checkpoint("Deals")

    # Execution successfully finished, printout all data for prometheus
    # GENERATE SCRAPE TIME
    metrics.print("scrape_duration_seconds", value=(time.time() - START_TIME), collector="All")
    metrics.print("scrape_execution_succeed", value=1)

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

def get_api_and_token(api, path):
    if api:
        [token, api] = api.split(":", 1)
        [_, _, addr, _, port, proto] = api.split("/", 5)
        url = f"{proto}://{addr}:{port}/rpc/v0"
        return (token, url)
    with open(path.joinpath("token"), "r") as f:
        token = f.read()
    with open(path.joinpath("api"), "r") as f:
        [_, _, addr, _, port, proto] = f.read().split("/", 5)
    url = f"{proto}://{addr}:{port}/rpc/v0"
    return (token, url)

def main():
    """ main function """

    global START_TIME

    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", default=os.environ.get("FARCASTER_LOG_LEVEL", "INFO"))
    parser.add_argument("--daemon-api", default=os.environ.get("FULLNODE_API_INFO"))
    parser.add_argument("--daemon-path", default=os.environ.get("LOTUS_PATH", Path.home().joinpath(".lotus")), type=Path)
    parser.add_argument("--miner-api", default=os.environ.get("MINER_API_INFO"))
    parser.add_argument("--miner-path", default=os.environ.get("LOTUS_MINER_PATH", Path.home().joinpath(".lotusminer")), type=Path)
    parser.add_argument("--farcaster-path", default=os.environ.get("LOTUS_FARCASTER_PATH", Path.home().joinpath(".lotus-exporter-farcaster")), type=Path)
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), None))

    try:
        (daemon_token, daemon_url) = get_api_and_token(args.daemon_api, args.daemon_path)
    except Exception  as e_generic:
        raise DaemonError(e_generic)

    try:
        (miner_token, miner_url) = get_api_and_token(args.miner_api, args.miner_path)
    except Exception  as e_generic:
        raise MinerError(e_generic)

    # Start execution time mesurement
    START_TIME = time.time()

    # Create Metrics object
    metrics = Metrics()

    # Create Lotus object
    try:
        lotus = Lotus(miner_url, miner_token, daemon_url, daemon_token)
    except DaemonError as e_generic:
        metrics.terminate(e_generic, -1)
    except MinerError as e_generic:
        metrics.terminate(e_generic, -2)

    # Load config file to retrieve external wallet and vlookup
    addresses_config = load_toml(args.farcaster_path.joinpath("addresses.toml"))

    # execute the collector
    run(lotus, metrics, addresses_config)

if __name__ == "__main__":

    # Declare Global Variables
    START_TIME = None
    LOTUS_OBJ = None
    METRICS_OBJ = None

    main()