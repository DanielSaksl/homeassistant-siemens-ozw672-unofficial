import asyncio
import logging
import socket
import time

import urllib.parse as Parse
import json

import aiohttp

_LOGGER: logging.Logger = logging.getLogger(__package__)
class SiemensOzw672ApiClient:
    def __init__(
        self, host: str, protocol: str, username: str, password: str, session: aiohttp.ClientSession, timeout: int, retries: int
    ) -> None:
        """Siemens OZW672 API Client."""
        _LOGGER.debug("OZW Init")
        self._host = host
        self._protocol = protocol
        self._username = username
        self._password = password
        self._session = session
        self._sessionid = "None"
        self._dpdata = None 
        self._timeout = timeout
        self._retries = retries

    async def async_get_sessionid(self) -> bool:
        """Login to the OZW672 and get a SessionID"""
        url=self._protocol + "://" + self._host + "/api/auth/login.json?user=" + self._username + "&pwd=" + Parse.quote(self._password)
        _LOGGER.debug(f"OZW Login to host: {self._host}")
        response = await self.api_wrapper("get_preauth", url)
        success = response["Result"]["Success"]
        if (success == "true"): 
            self._sessionid = response["SessionId"]
            return True
        _LOGGER.debug(f"Failed to Login: {response}")
        return False

    async def async_get_menu_node(self, node_id: str) -> dict | None:
        """Return one menu-tree node; callers decide whether to traverse further."""
        url=self._protocol + "://" + self._host + "/api/menutree/list.json?SessionId=" + self._sessionid +"&Id=" + node_id
        response = await self.api_wrapper("get", url)
        if response["Result"]["Success"] == "true":
            return response
        return None

    async def async_get_data(self, datapoints) -> dict:
        """Get the Data for multiple datapoints from the OZW6722."""
        start_time = time.time()
        _LOGGER.debug(f"async_get_data Getting data for datapoints : {datapoints}")
        consolidated_response={}
        for dp in datapoints:
            if (type(dp) == str):
                dpdata = json.loads(dp)
            else:
                dpdata = dp
            id = dpdata["Id"]
            url=self._protocol + "://" + self._host + "/api/menutree/read_datapoint.json?SessionId=" + self._sessionid +"&Id=" + id
            response = await self.api_wrapper("get", url)
            _LOGGER.debug(f"async_get_data response : {response}")
            if (response["Result"]["Success"] == "true"):
                if (response["Data"]["Value"] == '----'):
                    response["Data"]["Value"] = '0'
                consolidated_response[id]=response
        elapsed_time = time.time() - start_time
        if elapsed_time > 60:
            _LOGGER.warn(f"OZW672 Data Poll time exceeding 60 seconds. Last Poll Time: {round(elapsed_time)} seconds")
        _LOGGER.debug(f"OZW672 Data Poll time: {round(elapsed_time)} seconds")
        return consolidated_response
        # Sample response {"Data": {"Type": "Enumeration", "Value": "On", "Unit": ""}, "Result": {"Success": "true"}}

    async def async_write_data(self, datapoint, value) -> dict:
        """Write the Data for a single datapoints to the OZW6722."""
        _LOGGER.debug(f"async_get_data Writing data for datapoint : {datapoint}")
        if (type(datapoint) == str):
            dpdata = json.loads(datapoint)
        else:
            dpdata = datapoint
        id = dpdata["Id"]
        hasValid='false'
        dptype = dpdata["DPDescr"]["Type"]
        if (dptype == "Numeric"): # and ("HasValid" in dpdata["DPDescr"]):
            hasValid='true'
        url=self._protocol + "://" + self._host + "/api/menutree/write_datapoint.json?SessionId=" + self._sessionid +"&Id=" + id + "&Type=" + dptype + "&Value=" + value
        if (hasValid == 'true'):
            url=url + '&IsValid=true'
        response = await self.api_wrapper("get", url)
        _LOGGER.debug(f"async_get_data Datapoint Data response : {response}")
        if (response["Result"]["Success"] == "true"):
            _LOGGER.debug(f"GetData Response: {response}")
            return response
        else:
            return {}


    async def async_get_data_descr(self, datapoints, values) -> dict:
        """Get metadata for explicitly requested datapoints."""
        _LOGGER.debug(f"async_get_data_descr Getting data descriptions for datapoints : {datapoints}")
        consolidated_response={}
        for dp in datapoints:
            if (type(dp) == str):
                dpjson = json.loads(dp)
            else:
                dpjson = dp
            id = dpjson["Id"]
            dpdata = values[id]
            writeable = dpjson["WriteAccess"]
            url=self._protocol + "://" + self._host + "/api/menutree/datapoint_desc.json?SessionId=" + self._sessionid +"&Id=" + id       
            response = await self.api_wrapper("get", url)
            if (response["Result"]["Success"] == "true"):
                _LOGGER.debug(f"DatapointItem description reponse: {response}")
                # This maps the metadata returned for a single manually requested
                # datapoint to its Home Assistant platform.
                # Enumeration + Writeable + NOT On/Off = Select Entity
                # Enumeration + Writeable + On/Off = Switch
                # RadioButton/Enumeration + NOT Writeable + On/Off = BinarySensor
                # Number + Writeable + Percent/Temp = Number
                # Number + NOT Writeable + Percent/Temp = Sensor
                # Number + Writeable/NOT Writeable + OtherType = Sensor
                # Everything Else = Sensor
                ###
                if response["Description"]["Type"] == "Enumeration":
                    if writeable == "true":
                        if dpdata["Data"]["Value"] in ['On', 'Off'] :
                            response["Description"]["HAType"] = "switch"
                        else:
                            response["Description"]["HAType"] = "select" 
                    else:
                        if dpdata["Data"]["Value"] in ['On', 'Off'] :
                            response["Description"]["HAType"] = "binarysensor"
                        else:
                            response["Description"]["Enums"] = []  #Some Enums are huge - don't need them for read only sensors.
                            response["Description"]["HAType"] = "sensor"
                elif response["Description"]["Type"] in ("RadioButton", "Boolean", "Digital"):
                    if writeable == "true":
                        response["Description"]["HAType"] = "switch"
                    else:
                        if dpdata["Data"]["Value"] in ['On', 'Off'] :
                            response["Description"]["HAType"] = "binarysensor"
                        else:
                            response["Description"]["HAType"] = "sensor"
                elif response["Description"]["Type"] == "Numeric":
                    if writeable == "true" and response["Description"]["Unit"] in ['°C', '°F', 'K', '%', 'kWh', 'Wh']:
                        response["Description"]["HAType"] = "number"
                    else:
                        response["Description"]["HAType"] = "sensor"
                elif response["Description"]["Type"] == "TimeOfDay":
                    if writeable == "true":
                        response["Description"]["HAType"] = "time"
                    else:
                        response["Description"]["HAType"] = "sensor"
                else:   
                        response["Description"]["HAType"] = "sensor"
                # A writable numeric value must remain controllable regardless of
                # its engineering unit (for example hours or a vendor-specific unit).
                if response["Description"]["Type"] == "Numeric" and writeable == "true":
                    response["Description"]["HAType"] = "number"
                consolidated_response[id]=response
        _LOGGER.debug(f"async_get_data_descr DatapointItem description reponse: {consolidated_response}")
        return consolidated_response

    async def api_wrapper(
        self, method: str, url: str, data: dict = None, headers: dict = None,
        _reauth_attempted: bool = False
    ) -> dict:
        """Get information from the OZW WebAPI."""
        if data is None:
            data = {}
        if headers is None:
            headers = {}

        for x in range(self._retries):  #### YES - WE NEED TO RETRY OCCASSIONALY
            try:
                async with asyncio.timeout(self._timeout):
                    if method == "get_preauth":
                        response = await self._session.get(url, headers=headers,verify_ssl=False)
                        jsonresponse = await response.json()
                        _LOGGER.debug(f"PREAuth: {jsonresponse}")
                        return jsonresponse
                    elif method == "get":
                        cache_sessionid = self._sessionid
                        logurl=url.replace(f"SessionId={cache_sessionid}", "SessionId=XXXXXX")
                        _LOGGER.debug(f"HTTP GET url: {logurl}")
                        response = await self._session.get(url, headers=headers,verify_ssl=False)
                        jsonresponse = await response.json()
                        _LOGGER.debug(f"API GET: {jsonresponse}")
                        if (jsonresponse["Result"]["Success"] == "false"):
                            if (jsonresponse["Result"]["Error"]["Nr"] in ['1','2']):
                                if _reauth_attempted:
                                    # Re-authenticating did not help. Returning rather than
                                    # recursing again, which previously looped until
                                    # RecursionError when the session kept being rejected.
                                    _LOGGER.error(
                                        "Re-authentication did not resolve session error for url: %s",
                                        logurl,
                                    )
                                    return jsonresponse
                                await self.async_get_sessionid()
                                # Search and replace SessionId
                                newurl = url.replace(f"SessionId={cache_sessionid}", f"SessionId={self._sessionid}")
                                return await self.api_wrapper("get", newurl, _reauth_attempted=True)
                            else :
                                _LOGGER.error(f'Failed API call with error: {jsonresponse["Result"]["Error"]["Txt"]} for url:{logurl}')
                                return jsonresponse
                        else:
                            return jsonresponse

            except asyncio.TimeoutError as exception:
                _LOGGER.error(
                    "Timeout error fetching information from %s - %s",
                    url,
                    exception,
                )
                if x < self._retries:
                    _LOGGER.error("**** Module will retry ****")
                    pass

            except (KeyError, TypeError) as exception:
                _LOGGER.error(
                    "Error parsing information from %s - %s",
                    url,
                    exception,
                )
            except (aiohttp.ClientError, socket.gaierror) as exception:
                _LOGGER.error(
                    "Error fetching information from %s - %s",
                    url,
                    exception,
                )
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.error("Something really wrong happened! - %s", exception)
