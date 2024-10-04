#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=C0301, W0511, W0603, W0703, R0914, R0912, R0915, R0902, R0201, C0302, C0103, W1202
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

# Release v4.0.0
# Boost Support
# Introducing graphql

# Release v3.0.2
#   - Add --debug

# Release v3
#   - NEW Expired sectors (dashboard + exporter)
#   - NEW Add Deal transfers Storage and retreival markets (dashboard + exporter)
#   - NEW CC-upgrade view (dashboard + exporter)
#   - NEW Support market node (support market node locally or remotely deployed) (community request @BenjaminH)
#   - Installation scripts now included a Autoconfiguration assistant detecting a wide range of architecture
#   - Code is now object oriented, these objects exposed enhanced methods that are exposed to be reused by external programs.
#   - NEW support of multiple miners on the same server (community request @PatHoo)

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
import datetime
import toml
import multibase
import aiohttp
import traceback
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.aiohttp import log as aiohttp_logger

VERSION = "v3.0.2"

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

class MarketsError(Error):
    """Customer Exception to identify error coming from the markets. Used  for the dashboard Status panel"""

class DaemonError(Error):
    """Customer Exception to identify error coming from the daemon. Used  for the dashboard Status panel"""

class BoostError(Error):
    """Customer Exception to identify error coming from boost. Used  for the dashboard Status panel"""


class Lotus():
    """Lotus class is a common parent class to Miner and Daemon Class"""
    target = "lotus"
    Error = Error

    actor_type = {
        "system":           "System",
        "init":             "Init",
        "reward":           "Reward",
        "cron":             "Cron",
        "storagepower":     "StoragePower",
        "storagemarket":    "StorageMarket",
        "verifiedregistry": "VerifiedRegistry",
        "account":          "Account",
        "multisig":         "Multisig",
        "paymentchannel":   "PaymentChannel",
        "storageminer":     "StorageMiner"
    }

    message_type = {"Account":
                        [
                            "Constructor",
                            "PubkeyAddress",
                            "AuthenticateMessage",
                            "UniversalReceiverHook"],

                    "Init":
                        [
                            "Constructor",
                            "Exec",
                            "Exec4"],

                    "Cron":
                        [
                            "Constructor",
                            "EpochTick"],

                    "DatacapToken":
                        [
                            "Constructor",
                            "Mint",
                            "Destroy",
                            "Name",
                            "Symbol",
                            "TotalSupply",
                            "BalanceOf",
                            "Transfer",
                            "TransferFrom",
                            "IncreaseAllowance",
                            "DecreaseAllowance",
                            "RevokeAllowance",
                            "Burn",
                            "BurnFrom",
                            "Allowance"],

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
                            "LockBalance"
                            "UniversalReceiverHook",
                            "ListSignersAndThreshold"],

                    "PaymentChannel":
                        [
                            "Constructor",
                            "UpdateChannelState",
                            "Settle",
                            "Collect"
                            "ListFromTo",
                            "GetRedeemedAmount"],

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
                            "CronTick"
                            "GetBalance",
                            "GetDealDataCommitment",
                            "GetDealClient",
                            "GetDealProvider",
                            "GetDealLabel",
                            "GetDealTerm",
                            "GetDealEpochPrice",
                            "GetDealClientCollateral",
                            "GetDealProviderCollateral",
                            "GetDealVerified",
                            "GetDealActivation"],
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
                            "CurrentTotalPower",
                            "NetworkRawPower",
                            "MinerRawPower",
                            "Get miner count, consensus count",
                            "Compute pledge collateral for new sector",
                            "Get network bytes committed?",
                            "Get network total pledge collateral?",
                            "Get network epoch QA power",
                            "Get network epoch pledge collateral",
                            "Get miner's QA power"],
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
                            "DisputeWindowedPoSt",
                            "PreCommitSectorBatch",
                            "ProveCommitAggregate",
                            "ProveReplicaUpdates",
                            "PreCommitSectorBatch2",
                            "ProveReplicaUpdates2",
                            "ChangeBeneficiary",
                            "GetBeneficiary",
                            "ExtendSectorExpiration2",
                            "GetOwner",
                            "IsControllingAddress",
                            "GetSectorSize",
                            "GetVestingFunds",
                            "GetAvailableBalance",
                            "Read peer ID, multiaddr",
                            "Read pre-commit deposit",
                            "Read initial pledge total",
                            "Read fee debt"],

                    "VerifiedRegistry":
                        [
                            "Constructor",
                            "AddVerifier",
                            "RemoveVerifier",
                            "AddVerifiedClient",
                            "RemoveVerifiedClientDataCap",
                            "RemoveExpiredAllocations",
                            "ClaimAllocations",
                            "GetClaims",
                            "ExtendClaimTerms",
                            "RemoveExpiredClaims",
                            "UniversalReceiverHook",
                            "List/get allocations",
                            "List claims",
                            "List/check verifiers"]
                    }


    transfer_status_name = [
        "Requested",
        "Ongoing",
        "TransferFinished",
        "ResponderCompleted",
        "Finalizing",
        "Completing",
        "Completed",
        "Failing",
        "Failed",
        "Cancelling",
        "Cancelled",
        "InitiatorPaused",
        "ResponderPaused",
        "BothPaused",
        "ResponderFinalizing",
        "ResponderFinalizingTransferFinished",
        "ChannelNotFoundError"]

    def __init__(self, url, token):
        self.url = url
        self.token = token

    @Error.wrap
    def get(self, method, params):
        """Send a request to the daemon API / This function rely on the function that support async, but present a much simpler interface"""
        result = self.get_multiple([[method, params]])[0]

        if result is None:
            raise DaemonError(f"API returned nothing could be an incorrect API key\nTarget : {self.target}\nMethod : {method}\nParams : {params}\nResult : {result}")
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

class Daemon(Lotus):
    """Lotus Daemon class """
    target = "daemon"
    Error = DaemonError
    __chain_head = None
    __known_addresses = {}
    __local_wallet_list = None
    actor_cid = {}

    @Error.wrap
    def __init__(self, url, token):
        self.url = url
        self.token = token
        self.network_version = self.get("StateNetworkVersion", [self.tipset_key()])["result"]
        for actor, cid in self.get("StateActorCodeCIDs", [self.network_version])["result"].items():
            self.actor_cid[cid["/"]] = actor

    @Error.wrap
    def chain_head(self):
        """ Return chain_head is already retrieved or retrieve it for the chain"""
        if self.__chain_head is None:
            self.__chain_head = self.get("ChainHead", [])["result"]
        return self.__chain_head

    @Error.wrap
    def tipset_key(self):
        """ Return  tipset_key """
        return self.chain_head()["Cids"]

    @Error.wrap
    def basefee(self):
        """ Return basefee """
        return self.chain_head()["Blocks"][0]["ParentBaseFee"]

    @Error.wrap
    def add_known_addresses(self, *args, **kwargs):
        """ Add new addresses to the vlookup database"""
        return self.__known_addresses.update(*args, **kwargs)

    @Error.wrap
    def _get_actor_type(self, actor_code):
        try:
            a_type = self.actor_cid[actor_code]
        except Exception:
            raise Exception(f'Cannot decode actor_code {actor_code}')

        if a_type in self.__class__.actor_type.keys():
            return self.__class__.actor_type[a_type]

        raise Exception(f'Unknown actor_type {a_type} derived from actor_code : {actor_code}')

    @Error.wrap
    def address_lookup(self, input_addr):
        """ The function lookup an address and return the corresponding name from the chain or from the know_addresses table"""

        # if its in the lookup table, return it straight Away
        try:
            return self.__known_addresses[input_addr]
        except Exception:
            pass

        # If not need to look for the shortname and address
        # Check if the input address in a shortname
        if input_addr.startswith("f0"):

            # set the shortname
            name = input_addr

            # lookup for the address
            # Retrieve actor type
            try:
                actor = self.get("StateGetActor", [name, self.tipset_key()])["result"]["Code"]["/"]
                assert self._get_actor_type(actor) == "Account"
                addr = self.get("StateAccountKey", [input_addr, self.tipset_key()])["result"]
            except Exception:
                # if it failed set address to whatever we have
                addr = input_addr

        # If the input adress is really an address
        else:
            addr = input_addr

            # lookup for the shortname
            try:
                name = self.get("StateLookupID", [addr, self.tipset_key()])["result"]
            except Exception:
                # If the lookup failed (should not) lets create a nice short address
                name = addr[0:5] + "..." + addr[-5:]

        # AT THAT POINT we have a name and an adress

        # Return the name based on the following priority
        # If in the known address table
        if name in self.__known_addresses:
            return self.__known_addresses[name]

        if addr in self.__known_addresses:
            return self.__known_addresses[addr]

        return name

    @Error.wrap
    def __get_message_type(self, address, method):
        """ Return message_type of a given message.

        The code is based from an extract from : https://github.com/filecoin-project/specs-actors/blob/7d06c2806ff09868abea9e267ead2ada8438e077/actors/builtin/methods.go"""

        try:
            actor = self.get("StateGetActor", [address, self.tipset_key()])
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

    @Error.wrap
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
        proven_deadlines = self.get("StateMinerDeadlines", [miner_id, self.tipset_key()])

        # Init the structures that will contains all the deadlines information
        deadlines_info = {}
        deadlines_info["cur"] = self.get("StateMinerProvingDeadline", [miner_id, self.tipset_key()])["result"]

        number_of_dls = deadlines_info["cur"]["WPoStPeriodDeadlines"]

        deadlines_info["deadlines"] = {}
        for c_dl in range(number_of_dls):
            dl_id = (deadlines_info["cur"]["Index"] + c_dl) % number_of_dls

            partitions = self.get("StateMinerPartitions", [miner_id, dl_id, self.tipset_key()])
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

    @Error.wrap
    def get_deal_info_enhanced(self, deal_id):
        """ Return deald information with lookup on addresses."""
        try:
            deal_info = self.get("StateMarketStorageDeal", [deal_id, self.tipset_key()])["result"]
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
            deal["Client"] = self.address_lookup(deal["Client"])
            deal["Provider"] = self.address_lookup(deal["Provider"])
        return deal

    @Error.wrap
    def get_mpool_pending_enhanced(self, filter_from_address: list = None):
        """ Return an enhanced version of mpool pending with additionnal information : lookup on address / Method Type / etc ...

        If these information are useles, better call directly : daemon.get("MpoolPending",...)"""

        msg_list = []

        mpoolpending = self.get("MpoolPending", [self.tipset_key()])

        # Go through all messages and add informations
        for msg in mpoolpending["result"]:
            if not filter_from_address or msg["Message"]["From"] in filter_from_address:

                # Add actor_type and methode_type
                msg["Message"]["actor_type"], msg["Message"]["method_type"] = self.__get_message_type(msg["Message"]["To"], msg["Message"]["Method"])

                # Prettry print To address
                msg["Message"]["display_to"] = self.address_lookup(msg["Message"]["To"])

                # Prettyprint From addresses
                msg["Message"]["display_from"] = self.address_lookup(msg["Message"]["From"])

                msg_list.append(msg["Message"])

        return msg_list

    @Error.wrap
    def __get_local_wallet_list(self):
        """ retrieve local wallet list, return cache version if already executed """
        if self.__local_wallet_list is None:
            self.__local_wallet_list = self.get("WalletList", [])["result"]
        return self.__local_wallet_list

    @Error.wrap
    def get_wallet_list_enhanced(self, miner_id, external_wallets=None):
        """ return wallet enrich with addresses lookp and external wallet added"""

        external_wallets = external_wallets or {}

        res = {}

        # 1 Add wallet adresses to the loop and manage the case where wallet adress doesnt exist onchain because never get any transaction
        walletlist = self.__get_local_wallet_list()

        for addr in walletlist:
            try:
                balance = self.get("WalletBalance", [addr])["result"]
            except Exception as e_generic:
                logging.warning(f"cannot retrieve {addr} balance : {e_generic}")
                continue

            # Add address to the list
            res[addr] = {}
            res[addr]["balance"] = balance
            res[addr]["name"] = self.address_lookup(addr)

            try:
                verified_result = self.get("StateVerifiedClientStatus", [addr, self.tipset_key()])
                res[addr]["verified_datacap"] = verified_result["result"]
            except Exception:
                res[addr]["verified_datacap"] = 0

        # 2 Add miner balance
        res[miner_id] = {}
        res[miner_id]["balance"] = self.get("StateMinerAvailableBalance", [miner_id, self.tipset_key()])["result"]
        res[miner_id]["name"] = miner_id
        res[miner_id]["verified_datacap"] = self.get("StateVerifiedClientStatus", [miner_id, self.tipset_key()])["result"]

        # 3 Add external_wallets :
        for addr in external_wallets:
            try:
                balance = self.get("WalletBalance", [addr])["result"]
            except Exception as e_generic:
                logging.warning(f"cannot retrieve {addr} balance : {e_generic}")
                continue

            # Add address to the list
            res[addr] = {}
            res[addr]["balance"] = balance
            res[addr]["name"] = external_wallets[addr]

            try:
                verified_result = self.get("StateVerifiedClientStatus", [addr, self.tipset_key()])
                res[addr]["verified_datacap"] = verified_result["result"]
            except Exception:
                res[addr]["verified_datacap"] = 0

        return res

    @Error.wrap
    def get_local_mpool_pending_enhanced(self, miner_id):
        """ Return local mpool messages """
        wallet_list = self.get_wallet_list_enhanced(miner_id).keys()
        return self.get_mpool_pending_enhanced(wallet_list)

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

class Markets(Lotus):
    """ Markets class"""
    target = "markets"
    Error = MarketsError

    @Error.wrap
    def get_market_info_enhanced(self):
        """ create one structure with all the info related to storage and retreival market """
        res = {}

        res["storage"] = self.get("MarketGetAsk", [])["result"]["Ask"]
        res["storage"]["ConsiderOnlineDeals"] = self.get("DealsConsiderOnlineStorageDeals", [])["result"]
        res["storage"]["ConsiderOfflineDeals"] = self.get("DealsConsiderOfflineStorageDeals", [])["result"]

        res["retrieval"] = self.get("MarketGetRetrievalAsk", [])["result"]
        res["retrieval"]["ConsiderOnlineDeals"] = self.get("DealsConsiderOnlineRetrievalDeals", [])["result"]
        res["retrieval"]["ConsiderOfflineDeals"] = self.get("DealsConsiderOfflineRetrievalDeals", [])["result"]

        return res

    @Error.wrap
    def get_market_data_transfers_enhanced(self):
        """ return on-going data-transfers with status name """
        res = self.get("MarketListDataTransfers", [])["result"]
        print(res)
        sys.exit(3)
        for deal_id, transfer in enumerate(res):
            res[deal_id]["Status"] = self.transfer_status_name[transfer["Status"]]
        return res

    @Error.wrap
    def get_pending_publish_deals(self):
        pass

class Boost(Markets):
    """ Boost class"""
    target = "boost"
    Error = BoostError


    def __init__(self, url, token, graphql_url):
        self.url = url
        self.token = token
        self.graphql_url = graphql_url

        #Disable graphql log , to verbose by default
        aiohttp_logger.setLevel(logging.WARNING)

    @Error.wrap
    def get_pending_publish_deals(self):
        query = gql("query { dealPublish { Start Period Deals { PieceSize ClientAddress StartEpoch EndEpoch ProviderCollateral ID } } }")
        result = self.get_graphql(query)
        return result

    @Error.wrap
    def get_graphql(self, query):
        """Send a graphql query to boost, this function is not async yet"""

        transport = AIOHTTPTransport(url=self.graphql_url)
        client = Client(transport=transport, fetch_schema_from_transport=False)

        result = client.execute(query)

        return result


class Metrics():
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
        "miner_data_transfers"                      : {"type" : "gauge", "help": "data-transfer information"},
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
        "miner_pending_publish_deal"                : {"type" : "gauge", "help": "pending deal detail"},
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
        "miner_worker_ram_total"                    : {"type" : "gauge", "help": "worker server RAM"},
        "miner_worker_ram_tasks"                    : {"type" : "gauge", "help": "worker minimal memory used"},
        "miner_worker_ram_reserved"                 : {"type" : "gauge", "help": "worker memory reserved by lotus"},
        "miner_worker_vmem_total"                   : {"type" : "gauge", "help": "server Physical RAM + Swap"},
        "miner_worker_vmem_tasks"                   : {"type" : "gauge", "help": "worker VMEM used by on-going tasks"},
        "miner_worker_vmem_reserved"                : {"type" : "gauge", "help": "worker VMEM reserved by lotus"},
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

    def __init__(self, output=sys.stdout):
        self.__start_time = time.time()
        self.__last_collector_start_time = self.__start_time
        self._output = output
        self.add("local_time", value=int(self.__start_time))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *args):
        self.add("scrape_duration_seconds", value=(time.time() - self.__start_time), collector="All")

        # GENERATE EXIT CODE AND PRINT OUTPUT
        if exc_type is None:
            success = 1
        else:
            if exc_type == BoostError:
                success = -4
            elif exc_type == MarketsError:
                success = -3
            elif exc_type == MinerError:
                success = -2
            elif exc_type == DaemonError:
                success = -1
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

def collect(daemon, miner, markets, metrics, addresses_config):
    """ run metrics collection and export """

    # miner_id
    miner_id = miner.id()

    # Add KNOWN_ADDRESSES to Lotus OBJ
    if "known_addresses" in addresses_config.keys():
        daemon.add_known_addresses(addresses_config["known_addresses"])

    metrics.add("chain_basefee", value=daemon.basefee(), miner_id=miner_id)

    # CHAIN HEIGHT
    metrics.add("chain_height", value=daemon.chain_head()["Height"], miner_id=miner_id)
    metrics.checkpoint("ChainHead")

    # GENERATE CHAIN SYNC STATUS
    sync_status = daemon.get("SyncState", [])
    current_epoch = int((time.time() - 1598306400) / 30)
    for worker in sync_status["result"]["ActiveSyncs"]:
        try:
            if worker["Height"] > 0:
                diff_height = current_epoch - worker["Height"]
            else:
                diff_height = -1
        except Exception:
            diff_height = -1
        metrics.add("chain_sync_diff", value=diff_height, miner_id=miner_id, worker_id=sync_status["result"]["ActiveSyncs"].index(worker))
        metrics.add("chain_sync_status", value=worker["Stage"], miner_id=miner_id, worker_id=sync_status["result"]["ActiveSyncs"].index(worker))
    metrics.checkpoint("ChainSync")

    # GENERATE MINER INFO
    miner_version = miner.get("Version", [])
    metrics.checkpoint("Miner")

    # RETRIEVE MAIN ADDRESSES
    daemon_stats = daemon.get("StateMinerInfo", [miner_id, daemon.tipset_key()])
    miner_owner = daemon_stats["result"]["Owner"]
    miner_owner_addr = daemon.get("StateAccountKey", [miner_owner, daemon.tipset_key()])["result"]
    miner_worker = daemon_stats["result"]["Worker"]
    miner_worker_addr = daemon.get("StateAccountKey", [miner_worker, daemon.tipset_key()])["result"]

    # Add miner addresses to known_addresses lookup table
    daemon.add_known_addresses({miner_owner: "Local Owner", miner_owner_addr: "Local Owner", miner_worker: "Local Worker", miner_worker_addr: "Local Worker"})

    try:
        miner_control0 = daemon_stats["result"]["ControlAddresses"][0]
    except Exception:
        miner_control0 = miner_worker
    else:
        # Add miner addresses to known_addresses lookup table
        daemon.add_known_addresses({miner_control0: "Local control0"})

    miner_control0_addr = daemon.get("StateAccountKey", [miner_control0, daemon.tipset_key()])["result"]

    metrics.add("miner_info", value=1, miner_id=miner_id, version=miner_version["result"]["Version"], owner=miner_owner, owner_addr=miner_owner_addr, worker=miner_worker, worker_addr=miner_worker_addr, control0=miner_control0, control0_addr=miner_control0_addr)
    metrics.add("miner_info_sector_size", value=daemon_stats["result"]["SectorSize"], miner_id=miner_id)
    metrics.checkpoint("StateMinerInfo")

    # GENERATE DAEMON INFO
    daemon_network = daemon.get("StateNetworkName", [])
    daemon_network_version = daemon.get("StateNetworkVersion", [daemon.tipset_key()])
    daemon_version = daemon.get("Version", [])
    metrics.add("info", value=daemon_network_version["result"], miner_id=miner_id, version=daemon_version["result"]["Version"], network=daemon_network["result"])
    metrics.checkpoint("Daemon")

    # GENERATE WALLET
    if "external_wallets" in addresses_config:
        walletlist = daemon.get_wallet_list_enhanced(miner_id, addresses_config["external_wallets"])
    else:
        walletlist = daemon.get_wallet_list_enhanced(miner_id)

    for addr in walletlist.keys():
        metrics.add("wallet_balance", value=int(walletlist[addr]["balance"])/1000000000000000000, miner_id=miner_id, address=addr, name=walletlist[addr]["name"])
        if walletlist[addr]["verified_datacap"] is not None:
            metrics.add("wallet_verified_datacap", value=walletlist[addr]["verified_datacap"], miner_id=miner_id, address=addr, name=walletlist[addr]["name"])

    # Retrieve locked funds balance
    locked_funds = daemon.get("StateReadState", [miner_id, daemon.tipset_key()])
    for i in ["PreCommitDeposits", "LockedFunds", "FeeDebt", "InitialPledge"]:
        metrics.add("wallet_locked_balance", value=int(locked_funds["result"]["State"][i])/1000000000000000000, miner_id=miner_id, address=miner_id, locked_type=i)
    metrics.checkpoint("Balances")

    # GENERATE POWER
    powerlist = daemon.get("StateMinerPower", [miner_id, daemon.tipset_key()])
    for minerpower in powerlist["result"]["MinerPower"]:
        metrics.add("power", value=powerlist["result"]["MinerPower"][minerpower], miner_id=miner_id, scope="miner", power_type=minerpower)
    for totalpower in powerlist["result"]["TotalPower"]:
        metrics.add("power", value=powerlist["result"]["TotalPower"][totalpower], miner_id=miner_id, scope="network", power_type=totalpower)

    # Mining eligibility
    base_info = daemon.get("MinerGetBaseInfo", [miner_id, daemon.chain_head()["Height"], daemon.tipset_key()])

    if base_info["result"] is None:
        logging.error(f'MinerGetBaseInfo returned no result')
        logging.info(f'KNOWN_REASON your miner needs to have a power >0 for Farcaster to work. Its linked to a Lotus API bug)')
        logging.info(f'SOLUTION restart your miner and node')
        metrics.add("scrape_execution_succeed", value=0)
        sys.exit(0)

    if base_info["result"]["EligibleForMining"]:
        eligibility = 1
    else:
        eligibility = 0
    metrics.add("power_mining_eligibility", value=eligibility, miner_id=miner_id)
    metrics.checkpoint("Power")

    # GENERATE MPOOL
    mpool_total = len(daemon.get("MpoolPending", [daemon.tipset_key()])["result"])
    local_mpool = daemon.get_local_mpool_pending_enhanced(miner_id)
    local_mpool_total = len(local_mpool)

    metrics.add("mpool_total", value=mpool_total, miner_id=miner_id)
    metrics.add("mpool_local_total", value=local_mpool_total, miner_id=miner_id)

    for msg in local_mpool:
        metrics.add("mpool_local_message", value=1, miner_id=miner_id, msg_from=msg["display_from"], msg_to=msg["display_to"], msg_nonce=msg["Nonce"], msg_value=msg["Value"], msg_gaslimit=msg["GasLimit"], msg_gasfeecap=msg["GasFeeCap"], msg_gaspremium=msg["GasPremium"], msg_method=msg["Method"], msg_method_type=msg["method_type"], msg_to_actor_type=msg["actor_type"])
    metrics.checkpoint("MPool")

    # GENERATE NET_PEERS
    daemon_netpeers = daemon.get("NetPeers", [])
    metrics.add("netpeers_total", value=len(daemon_netpeers["result"]), miner_id=miner_id)

    markets_netpeers = markets.get("NetPeers", [])
    metrics.add("miner_netpeers_total", value=len(markets_netpeers["result"]), miner_id=miner_id)
    metrics.checkpoint("NetPeers")

    # GENERATE NETSTATS XXX Verfier la qualité des stats ... lotus net, API et Grafana sont tous differents
    protocols_list = daemon.get("NetBandwidthStatsByProtocol", [])
    for protocol in protocols_list["result"]:
        metrics.add("net_protocol_in", value=protocols_list["result"][protocol]["TotalIn"], miner_id=miner_id, protocol=protocol)
        metrics.add("net_protocol_out", value=protocols_list["result"][protocol]["TotalOut"], miner_id=miner_id, protocol=protocol)

    protocols_list = markets.get("NetBandwidthStatsByProtocol", [])
    for protocol in protocols_list["result"]:
        metrics.add("miner_net_protocol_in", value=protocols_list["result"][protocol]["TotalIn"], miner_id=miner_id, protocol=protocol)
        metrics.add("miner_net_protocol_out", value=protocols_list["result"][protocol]["TotalOut"], miner_id=miner_id, protocol=protocol)

    net_list = daemon.get("NetBandwidthStats", [])
    metrics.add("net_total_in", value=net_list["result"]["TotalIn"], miner_id=miner_id)
    metrics.add("net_total_out", value=net_list["result"]["TotalOut"], miner_id=miner_id)

    net_list = markets.get("NetBandwidthStats", [])
    metrics.add("miner_net_total_in", value=net_list["result"]["TotalIn"], miner_id=miner_id)
    metrics.add("miner_net_total_out", value=net_list["result"]["TotalOut"], miner_id=miner_id)
    metrics.checkpoint("NetBandwidth")

    # GENERATE WORKER INFOS
    workerstats = miner.get("WorkerStats", [])
    # XXX 1.2.1 introduce a new worker_id format. Later we should delete it, its a useless info.
    #print("# HELP lotus_miner_worker_id All lotus worker information prfer to use workername than workerid which is changing at each restart")
    #print("# TYPE lotus_miner_worker_id gauge")

#
# 37
                 # TOTAL RAM
# 36             ramTotal := stat.Info.Resources.MemPhysical

                 # RAM USED
# 35             ramTasks := stat.MemUsedMin

                # RAM RESERVED
# 34             ramUsed := stat.Info.Resources.MemUsed
# 33             var ramReserved uint64 = 0
# 32             if ramUsed > ramTasks {
# 31                 ramReserved = ramUsed - ramTasks
# 30             }
# 29             ramBar := barString(float64(ramTotal), float64(ramReserved), float64(ramTasks))
# 28
# 27             fmt.Printf("\tRAM:  [%s] %d%% %s/%s\n", ramBar,
# 26                 (ramTasks+ramReserved)*100/stat.Info.Resources.MemPhysical,
# 25                 types.SizeStr(types.NewInt(ramTasks+ramUsed)),
# 24                 types.SizeStr(types.NewInt(stat.Info.Resources.MemPhysical)))
# 23
# 22             vmemTotal := stat.Info.Resources.MemPhysical + stat.Info.Resources.MemSwap
# 21             vmemTasks := stat.MemUsedMax
# 20             vmemUsed := stat.Info.Resources.MemUsed + stat.Info.Resources.MemSwapUsed
# 19             var vmemReserved uint64 = 0
# 18             if vmemUsed > vmemTasks {
# 17                 vmemReserved = vmemUsed - vmemTasks
# 16             }
# 15             vmemBar := barString(float64(vmemTotal), float64(vmemReserved), float64(vmemTasks))
# 14
# 13             fmt.Printf("\tVMEM: [%s] %d%% %s/%s\n", vmemBar,
# 12                 (vmemTasks+vmemReserved)*100/vmemTotal,
# 11                 types.SizeStr(types.NewInt(vmemTasks+vmemReserved)),
# 10                 types.SizeStr(types.NewInt(vmemTotal)))
#  9
#

    worker_list = {}
    for (worker_id, stat) in workerstats["result"].items():
        worker_host = stat["Info"]["Hostname"]
        cpus = stat["Info"]["Resources"]["CPUs"]
        gpus = len(stat["Info"]["Resources"]["GPUs"])

        # SMALL HACK FOR RETROCOMPATIBILITY CAN BE REMOVED IN NEW LOTUS VERSION WE NEED TO CALCULATE MEMRESERVED
        if "MemReserved" not in stat["Info"]["Resources"].keys():
            # TOTAL RAM AVAILABLE
            ram_total = stat["Info"]["Resources"]["MemPhysical"]

            # TOTAL RAM USED BY ONGOING TASKS
            ram_tasks = stat["MemUsedMin"]

            # TOTAL RAM USED (really used + RESERVED
            ram_used = stat["Info"]["Resources"]["MemUsed"]

            # TOTAL RAM RESERVED
            ram_reserved = 0
            if ram_used > ram_tasks:
                ram_reserved = ram_used - ram_tasks

            # TOTAL VMEM
            vmem_total = ram_total + stat["Info"]["Resources"]["MemSwap"]

            # TOTAL VMEM USED BY ONGOING TASKS
            vmem_tasks = stat["MemUsedMax"]

            # TOTAL VMEM RESERVER + REALLY USED
            vmem_used = ram_used + stat["Info"]["Resources"]["MemSwapUsed"]

            # TOTAL VMEM RESERVED
            vmem_reserved = 0
            if vmem_used > vmem_tasks:
                vmem_reserved = vmem_used - vmem_tasks

        else:
            # TOTAL RAM AVAILABLE
            ram_total = stat["Info"]["Resources"]["MemPhysical"]

            # TOTAL RAM USED BY ONGOING TASKS
            ram_tasks = stat["MemUsedMin"]

            # TOTAL RAM RESERVED
            ram_reserved = stat["Info"]["Resources"]["MemReserved"]

            # TOTAL RAM USED (really used + RESERVED
            ram_used = ram_tasks + ram_reserved

            # TOTAL VMEM
            vmem_total = ram_total + stat["Info"]["Resources"]["MemSwap"]

            # TOTAL VMEM USED BY ONGOING TASKS
            vmem_tasks = stat["MemUsedMax"]

            # TOTAL VMEM USED REALLY USED + RESERVED // HERE THERE IS NO SWAP RESERVED
            vmem_used = vmem_tasks + ram_reserved

            # TOTAL MEM RESERVER, HERE ONLY RAM
            vmem_reserved = ram_reserved

        if stat["GpuUsed"]:
            gpu_used = 1
        else:
            gpu_used = 0
        cpu_used = stat["CpuUse"]

        # TEST to avoid duplicate entries incase 2 workers on the same machine. This could be remove once PL will include URL in WorkerStats API call
        if worker_host not in worker_list.keys():
            worker_list[worker_host] = 1

            metrics.add("miner_worker_cpu", value=cpus, miner_id=miner_id, worker_host=worker_host)
            metrics.add("miner_worker_gpu", value=gpus, miner_id=miner_id, worker_host=worker_host)
            metrics.add("miner_worker_ram_total", value=ram_total, miner_id=miner_id, worker_host=worker_host)
            metrics.add("miner_worker_ram_reserved", value=ram_reserved, miner_id=miner_id, worker_host=worker_host)
            metrics.add("miner_worker_ram_tasks", value=ram_tasks, miner_id=miner_id, worker_host=worker_host)
            metrics.add("miner_worker_vmem_total", value=vmem_total, miner_id=miner_id, worker_host=worker_host)
            metrics.add("miner_worker_vmem_reserved", value=vmem_reserved, miner_id=miner_id, worker_host=worker_host)
            metrics.add("miner_worker_vmem_tasks", value=vmem_tasks, miner_id=miner_id, worker_host=worker_host)
            metrics.add("miner_worker_gpu_used", value=gpu_used, miner_id=miner_id, worker_host=worker_host)
            metrics.add("miner_worker_cpu_used", value=cpu_used, miner_id=miner_id, worker_host=worker_host)
    metrics.checkpoint("Workers")

    # GENERATE JOB INFOS
    workerjobs = miner.get("WorkerJobs", [])
    for (wrk, job_list) in workerjobs["result"].items():
        for job in job_list:
            job_id = job['ID']['ID']
            sector = str(job['Sector']['Number'])

            try:
                worker_host = workerstats["result"][wrk]["Info"]["Hostname"]
            except Exception:
                # sometime WorkerJobs return invalid worker_id like 0000-000000-0000... in that case return unknown
                worker_host = "unknown"
            task = str(job['Task'])
            job_start_time = str(job['Start'])
            run_wait = str(job['RunWait'])
            job_start_epoch = time.mktime(time.strptime(job_start_time[:19], '%Y-%m-%dT%H:%M:%S'))
            metrics.add("miner_worker_job", value=(time.time() - job_start_epoch), miner_id=miner_id, job_id=job_id, worker_host=worker_host, task=task, sector_id=sector, job_start_time=job_start_time, run_wait=run_wait)
    metrics.checkpoint("Jobs")

    # GENERATE JOB SCHEDDIAG
    scheddiag = miner.get("SealingSchedDiag", [True])

    if scheddiag["result"]["SchedInfo"]["Requests"]:
        for req in scheddiag["result"]["SchedInfo"]["Requests"]:
            sector = req["Sector"]["Number"]
            task = req["TaskType"]
            metrics.add("miner_worker_job", miner_id=miner_id, job_id="", worker="", task=task, sector_id=sector, start="", run_wait="99")
    metrics.checkpoint("SchedDiag")

    # GENERATE SECTORS
    sector_list = miner.get("SectorsList", [])

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
    details = miner.get_multiple(request_list)

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
            qa_power = daemon.qa_power_for_weight(size, duration, deal_weight, verified_weight)

        try:
            creation_date = detail["result"]["Log"][0]["Timestamp"]
        except Exception as exp:
            logging.warning(f"Sector {i} : cannot find sector creation date : {exp}")
            creation_date = 0
            pass
        packed_date = ""
        finalized_date = ""

        if detail["result"]["Log"]:
            creation_date = detail["result"]["Log"][0]["Timestamp"]

        for log in range(len(detail["result"]["Log"])):
            if detail["result"]["Log"][log]["Kind"] == "event;sealing.SectorPacked":
                packed_date = detail["result"]["Log"][log]["Timestamp"]
            if detail["result"]["Log"][log]["Kind"] == "event;sealing.SectorFinalized":
                finalized_date = detail["result"]["Log"][log]["Timestamp"]

        try:
            if detail["result"]["Log"][0]["Kind"] == "event;sealing.SectorStartCC":
                pledged = 1
            else:
                pledged = 0
        except Exception as exp:
            logging.warning(f"Sector {i} : cannot find sector kind, default to CC : {exp}")
            pledged = 1
            pass
        metrics.add("miner_sector_state", value=1, miner_id=miner_id, sector_id=sector, state=detail["result"]["State"], to_upgrade=detail["result"]["ToUpgrade"], pledged=pledged, deals=deals)
        metrics.add("miner_sector_weight", value=verified_weight, weight_type="verified", miner_id=miner_id, sector_id=sector)
        metrics.add("miner_sector_weight", value=deal_weight, weight_type="non_verified", miner_id=miner_id, sector_id=sector)
        metrics.add("miner_sector_qa_power", value=qa_power, miner_id=miner_id, sector_id=sector)

        if packed_date != "":
            metrics.add("miner_sector_event", value=packed_date, miner_id=miner_id, sector_id=sector, event_type="packed")
        if creation_date != "":
            metrics.add("miner_sector_event", value=creation_date, miner_id=miner_id, sector_id=sector, event_type="creation")
        if finalized_date != "":
            metrics.add("miner_sector_event", value=finalized_date, miner_id=miner_id, sector_id=sector, event_type="finalized")

        if detail["result"]["State"] not in ["Proving", "Removed"]:
            for deal in detail["result"]["Deals"]:
                if deal != 0:
                    deal_info = daemon.get_deal_info_enhanced(deal)
                    deal_is_verified = deal_info["VerifiedDeal"]
                    deal_size = deal_info["PieceSize"]
                    deal_price_per_epoch = deal_info["StoragePricePerEpoch"]
                    deal_provider_collateral = deal_info["ProviderCollateral"]
                    deal_client_collateral = deal_info["ClientCollateral"]
                    deal_start_epoch = deal_info["StartEpoch"]
                    deal_end_epoch = deal_info["EndEpoch"]
                    deal_client = deal_info["Client"]

                    metrics.add("miner_sector_sealing_deals_info", value=1, miner_id=miner_id, sector_id=sector, deal_id=deal, deal_is_verified=deal_is_verified, deal_price_per_epoch=deal_price_per_epoch, deal_provider_collateral=deal_provider_collateral, deal_client_collateral=deal_client_collateral, deal_size=deal_size, deal_start_epoch=deal_start_epoch, deal_end_epoch=deal_end_epoch, deal_client=deal_client)

    metrics.checkpoint("Sectors")

    # GENERATE DEADLINES
    deadlines = daemon.get_deadlines_enhanced(miner_id)
    metrics.add("miner_deadline_info", value=1, miner_id=miner_id, current_idx=deadlines["cur"]["Index"], current_epoch=deadlines["cur"]["CurrentEpoch"], current_open_epoch=deadlines["cur"]["Open"], wpost_period_deadlines=deadlines["cur"]["WPoStPeriodDeadlines"], wpost_challenge_window=deadlines["cur"]["WPoStChallengeWindow"])
    for dl_id, deadline in deadlines["deadlines"].items():
        metrics.add("miner_deadline_active_start", value=deadline["StartIn"], miner_id=miner_id, index=dl_id)
        metrics.add("miner_deadline_active_partitions_proven", value=deadline["ProvenPartition"], miner_id=miner_id, index=dl_id)
        metrics.add("miner_deadline_active_partitions", value=deadline["PartitionsCount"], miner_id=miner_id, index=dl_id)
        metrics.add("miner_deadline_active_sectors_all", value=deadline["AllSectorsCount"], miner_id=miner_id, index=dl_id)
        metrics.add("miner_deadline_active_sectors_recovering", value=deadline["RecoveringSectorsCount"], miner_id=miner_id, index=dl_id)
        metrics.add("miner_deadline_active_sectors_faulty", value=deadline["FaultySectorsCount"], miner_id=miner_id, index=dl_id)
        metrics.add("miner_deadline_active_sectors_active", value=deadline["ActiveSectorsCount"], miner_id=miner_id, index=dl_id)
        metrics.add("miner_deadline_active_sectors_live", value=deadline["LiveSectorsCount"], miner_id=miner_id, index=dl_id)
        for partition_id, partition in deadline["partitions"].items():
            for sector_id in partition.keys():
                is_active = "Active" in partition[sector_id]
                is_live = "Live" in partition[sector_id]
                is_recovering = "Recovering" in partition[sector_id]
                is_faulty = "Faulty" in partition[sector_id]
                metrics.add("miner_deadline_active_partition_sector", is_active=is_active, is_live=is_live, is_recovering=is_recovering, is_faulty=is_faulty, value=1, miner_id=miner_id, deadline_id=dl_id, partition_id=partition_id, sector_id=sector_id)
    metrics.checkpoint("Deadlines")


    # GENERATE STORAGE INFO
    for sto in miner.get_storagelist_enhanced():
        metrics.add("miner_storage_info", value=1, miner_id=miner_id, storage_id=sto["storage_id"], storage_url=sto["url"], storage_host_name=sto["host_name"], storage_host_ip=sto["host_ip"], storage_host_port=sto["host_port"], weight=sto["weight"], can_seal=sto["can_seal"], can_store=sto["can_store"], path=sto["path"])
        metrics.add("miner_storage_capacity", value=sto["capacity"], miner_id=miner_id, storage_id=sto["storage_id"])
        metrics.add("miner_storage_available", value=sto["available"], miner_id=miner_id, storage_id=sto["storage_id"])
        metrics.add("miner_storage_reserved", value=sto["reserved"], miner_id=miner_id, storage_id=sto["storage_id"])
    metrics.checkpoint("Storage")

    # GENERATE MARKET INFO
    market_info = markets.get_market_info_enhanced()
    metrics.add("miner_market_info", value=1,
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

    # GENERATE  DATA TRANSFERS XXX DISABLED AS NOT COMPATIBLE WITH BOOST, GENERATE DATA TRANSFER FOR ALL EXEISTING DEALS
#    data_transfers = markets.get_market_data_transfers_enhanced()
#    for transfer in data_transfers:
#        try:
#            voucher = json.loads(transfer["Voucher"])["Proposal"]["/"]
#        except Exception:
#            voucher = ""
#
#        metrics.add("miner_data_transfers", value=transfer["Transferred"],
#                    miner_id=miner_id,
#                    transfer_id=transfer["TransferID"],
#                    status=transfer["Status"],
#                    base_cid=transfer["BaseCID"]["/"],
#                    is_initiator=transfer["IsInitiator"],
#                    is_sender=transfer["IsSender"],
#                    voucher=voucher,
#                    message=transfer["Message"].replace("\n", "  ").replace('"', " "),
#                    other_peer=transfer["OtherPeer"],
#                    stages=transfer["Stages"])

    # GENERATE PENDINGDEALS
    pending_publish_deals = markets.get_pending_publish_deals()["dealPublish"]

    if pending_publish_deals and len(pending_publish_deals["Deals"]) > 0:
        # Remove microseconds because not managed by python then convert to epoch
        publish_start = pending_publish_deals["Start"]
        plus_position = publish_start.find("+")
        publish_start = publish_start[:plus_position-3] + publish_start[plus_position:]
        publish_start = datetime.datetime.strptime(publish_start, '%Y-%m-%dT%H:%M:%S.%f%z').strftime('%s')

        # Clean PublishINseconds
        publish_in_seconds = pending_publish_deals["Period"] / 1000000000

        for deal in pending_publish_deals["Deals"]:
            deal_size = int(deal["PieceSize"]["n"])
            deal_id = deal["ID"]
            client = daemon.address_lookup(deal["ClientAddress"])
            duration = int(deal["EndEpoch"]["n"])-int(deal["StartEpoch"]["n"])
            provider_collateral = int(deal["ProviderCollateral"]["n"])
            metrics.add("miner_pending_publish_deal", value=1, miner_id=miner_id, deal_size=deal_size, client=client, duration=duration, provider_collateral=provider_collateral, publish_start=publish_start, publish_in_seconds=publish_in_seconds, deal_id=deal_id)

#XXXBOOST    pending_publish_deals = markets.get("MarketPendingDeals", [])["result"]
#    pending_publish_deals= undef
#
#    if pending_publish_deals and len(pending_publish_deals["Deals"]) > 0:
#        # Remove microseconds because not managed by python then convert to epoch
#        publish_start = pending_publish_deals["PublishPeriodStart"]
#        plus_position = publish_start.find("+")
#        publish_start = publish_start[:plus_position-3] + publish_start[plus_position:]
#        publish_start = datetime.datetime.strptime(publish_start, '%Y-%m-%dT%H:%M:%S.%f%z').strftime('%s')
#
#        # Clean PublishINseconds
#        publish_in_seconds = pending_publish_deals["PublishPeriod"] / 1000000000
#
#        for deal in pending_publish_deals["Deals"]:
#            deal_size = deal["Proposal"]["PieceSize"]
#            deal_is_verified = deal["Proposal"]["VerifiedDeal"]
#            client = daemon.address_lookup(deal["Proposal"]["Client"])
#            duration = deal["Proposal"]["EndEpoch"]-deal["Proposal"]["StartEpoch"]
#            price_per_epoch = deal["Proposal"]["StoragePricePerEpoch"]
#            total_price = int(duration) * int(price_per_epoch)
#            provider_collateral = deal["Proposal"]["ProviderCollateral"]
#            metrics.add("miner_pending_publish_deal", value=1, miner_id=miner_id, deal_size=deal_size, deal_is_verified=deal_is_verified, client=client, duration=duration, price_per_epoch=price_per_epoch, total_price=total_price, provider_collateral=provider_collateral, publish_start=publish_start, publish_in_seconds=publish_in_seconds)
#
#

    metrics.checkpoint("Market")
    # XXX RAJOUTER : PublishPeriodStart / PublishINseconds / Expected collateral Against ProviderCollateral

    # GENERATE DEALS INFOS
    # XXX NOT FINISHED
    # publish_deals = miner.get("MarketPendingDeals", '[]'):
    # metrics.add("miner_pending_deals", value=1, miner_id=miner_id, deal_id=deal, deal_is_verified=deal_is_verified, deal_price_per_epoch=deal_price_per_epoch, deal_provider_collateral=deal_provider_collateral, deal_client_collateral=deal_client_collateral, deal_size=deal_size, deal_start_epoch=deal_start_epoch, deal_end_epoch=deal_end_epoch, deal_client=deal_client)
    # metrics.checkpoint("Deals")

    # XXX TODO
    # TODO :
    #   - manage market node
    #   - Support LOTUS PATH VARIABLES
    #   - Optimization by memoization
    #   - Control address
    # Bugs :
    #   Gerer le bug lier à l'absence de Worker (champs GPU vide, etc...)
    # Retrieval Market :
    #   GENERATE RETRIEVAL MARKET
    #   print(miner.get("MarketListRetrievalDeals",[]))
    #   GENERATE DATA TRANSFERS
    #   print(miner.get("MarketListDataTransfers",[]))
    #   Pending Deals
    #   MarketPendingDeals
    # Deals : MarketListIncompleteDeals
    # Others :
    #   A quoi correcpond le champs retry dans le SectorStatus
    #   rajouter les errors de sectors
    #   print(daemon.get("StateMinerFaults",[miner_id,LOTUS_OBJ.tipset_key()]))
    # Add Partition to Deadlines
    # - Add the list of sectors we can upgrade (maybe already there)
# DM lotus@lamia:~$ lotus-exporter-farcaster.py
# Traceback (most recent call last):
#   File "/usr/local/bin/lotus-exporter-farcaster.py", line 1303, in <module>
#     main()
#   File "/usr/local/bin/lotus-exporter-farcaster.py", line 1000, in main
#     walletlist = LOTUS_OBJ.get_wallet_list_enhanced()
#   File "/usr/local/bin/lotus-exporter-farcaster.py", line 676, in get_wallet_list_enhanced
#     res[addr]["verified_datacap"] = self.daemon.get_json("StateVerifiedClientStatus", [addr, self.tipset_key()])["result"]
# KeyError: 'result'

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
    for variable in "miner_api", "markets_api", "daemon_api", "markets_type":
        if variable not in config.keys():
            logging.error(f"{variable} not found in {config_file}")
            logging.info("Re-run the install.sh script or add it to the config file manually")
            sys.exit(0)

    with Metrics(output=output) as metrics:
        # Create the daemon Object instance
        try:
            daemon = Daemon(*get_url_and_token(config["daemon_api"]))
        except Exception as exp:
            raise DaemonError("config value daemon_ip " + str(exp))

        # Create the miner Object instance
        try:
            miner = Miner(*get_url_and_token(config["miner_api"]))
        except Exception as exp:
            raise MinerError("config value miner_ip " + str(exp))

        # Create the markets object instance
        if config["markets_type"] == "boost":
            if "boost_graphql" not in config.keys():
                raise BoostError("config value boost_graphql not set")
            if "boost_api" not in config.keys():
                raise BoostError("config value boost_api not set")
            try:
                markets = Boost(*get_url_and_token(config["boost_api"]), config["boost_graphql"])
            except Exception as exp:
                raise BoostError("config value boost_api " + str(exp))
        else:
            try:
                markets = Markets(*get_url_and_token(config["markets_api"]))
            except Exception as exp:
                raise MarketsError("config value markets_api " + str(exp))

        # Load addresses lookup config file to retrieve external wallet and vlookup
        addresses_config = load_toml(args.farcaster_config_folder.joinpath("addresses.toml"))

        # execute the collector
        collect(daemon, miner, markets, metrics, addresses_config)

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
