"""Configuration and manual datapoint management for Siemens OZW672."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers import selector

from .api import SiemensOzw672ApiClient
from .const import (
    CONF_DATAPOINTS,
    CONF_HOST,
    CONF_HTTPRETRIES,
    CONF_HTTPTIMEOUT,
    CONF_PASSWORD,
    CONF_PREFIX_FUNCTION,
    CONF_PREFIX_OPLINE,
    CONF_PROTOCOL,
    CONF_SCANINTERVAL,
    CONF_USERNAME,
    DEFAULT_HTTPRETRIES,
    DEFAULT_HTTPTIMEOUT,
    DEFAULT_SCANINTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
CONF_DATAPOINT_ID = "datapoint_id"


class SiemensOzw672FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up only the gateway connection; datapoints are managed later."""

    VERSION = 1
    MINOR_VERSION = 6
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            client = SiemensOzw672ApiClient(
                user_input[CONF_HOST], "https", user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD], async_create_clientsession(self.hass),
                DEFAULT_HTTPTIMEOUT, DEFAULT_HTTPRETRIES,
            )
            try:
                connected = await client.async_get_sessionid()
            except Exception:  # The API client already logs the underlying error.
                connected = False
            if connected:
                await self.async_set_unique_id(user_input[CONF_HOST].lower())
                self._abort_if_unique_id_configured()
                data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_PROTOCOL: "https",
                    CONF_DATAPOINTS: [],
                    # Kept for existing entity code and a useful device name.
                    "devicename": user_input[CONF_HOST],
                    CONF_PREFIX_FUNCTION: False,
                    CONF_PREFIX_OPLINE: False,
                }
                options = {CONF_SCANINTERVAL: user_input[CONF_SCANINTERVAL]}
                return self.async_create_entry(title=user_input[CONF_HOST], data=data, options=options)
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_SCANINTERVAL, default=DEFAULT_SCANINTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=10)
                ),
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SiemensOzw672OptionsFlowHandler()


class SiemensOzw672OptionsFlowHandler(config_entries.OptionsFlow):
    """Manual datapoint browser and entity manager."""

    def __init__(self):
        self._candidates: list[tuple[dict, dict]] = []
        self._datapoint_index: dict[str, dict] | None = None
        self._errors: dict[str, str] = {}
        self._browser_error = ""

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init", menu_options=["browser", "remove", "settings"]
        )

    async def async_step_browser(self, user_input=None):
        """Build an on-demand searchable picker from the OZW menu tree."""
        self._errors = {}
        if self._datapoint_index is None:
            try:
                self._datapoint_index = await self._build_datapoint_index()
            except Exception:
                _LOGGER.exception("Unable to build the OZW datapoint index")
                self._errors["base"] = "cannot_connect"
                self._datapoint_index = {}
        if user_input is not None:
            self._browser_error = ""
            selected_ids = user_input[CONF_DATAPOINT_ID]
            if isinstance(selected_ids, str):
                selected_ids = [selected_ids]
            self._candidates = []
            failures = []
            for datapoint_id in selected_ids:
                raw = self._datapoint_index.get(datapoint_id)
                if raw is None:
                    failures.append(f"{datapoint_id}: not found")
                    continue
                try:
                    self._candidates.append(await self._load_datapoint(raw))
                except Exception as err:
                    _LOGGER.exception(
                        "Unable to load manually requested datapoint %s", datapoint_id
                    )
                    failures.append(f"{datapoint_id}: {type(err).__name__}: {err}")

            if failures:
                self._browser_error = "; ".join(failures)
            if not self._candidates:
                self._errors["base"] = (
                    "datapoint_not_found" if not failures else "datapoint_processing_failed"
                )
                return await self.async_step_browser()
            if len(self._candidates) == 1:
                return await self.async_step_add_entity()
            return await self.async_step_add_entities()

        options = [
            selector.SelectOptionDict(
                value=internal_id,
                label=(
                    f'{internal_id} — {raw["Text"].get("Long", internal_id)} '
                    f'({raw["Text"].get("Id", "—")})'
                ),
            )
            for internal_id, raw in sorted(
                self._datapoint_index.items(),
                key=lambda item: item[1]["Text"].get("Long", "").casefold(),
            )
        ]
        return self.async_show_form(
            step_id="browser",
            data_schema=vol.Schema({
                vol.Required(CONF_DATAPOINT_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        multiple=True,
                    )
                )
            }),
            errors=self._errors,
            description_placeholders={"error": self._browser_error or "None"},
        )

    async def async_step_add_entity(self, user_input=None):
        """Show metadata and persist the explicitly approved datapoint."""
        if len(self._candidates) != 1:
            return await self.async_step_browser()
        candidate, candidate_data = self._candidates[0]
        if user_input is not None:
            self._save_candidates()
            return self.async_create_entry(title="", data=dict(self.config_entry.options))

        description = candidate["DPDescr"]
        enum_values = ", ".join(item["Text"] for item in description.get("Enums", [])) or "—"
        return self.async_show_form(
            step_id="add_entity",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": candidate["Name"],
                "value": str(candidate_data["Data"].get("Value", "")),
                "unit": candidate_data["Data"].get("Unit", "") or "—",
                "datatype": description.get("Type", "unknown"),
                "writable": "Yes" if candidate["WriteAccess"] == "true" else "No",
                "enums": enum_values,
                "entity_type": description["HAType"],
            },
        )

    async def async_step_add_entities(self, user_input=None):
        """Confirm adding every successfully loaded datapoint in a batch."""
        if len(self._candidates) < 2:
            return await self.async_step_browser()
        if user_input is not None:
            self._save_candidates()
            return self.async_create_entry(title="", data=dict(self.config_entry.options))

        return self.async_show_form(
            step_id="add_entities",
            data_schema=vol.Schema({}),
            description_placeholders={
                "count": str(len(self._candidates)),
                "error": self._browser_error or "None",
                "names": "\n".join(
                    f'{candidate["Id"]}: {candidate["Name"]}'
                    for candidate, _data in self._candidates
                ),
            },
        )

    def _save_candidates(self) -> None:
        """Save loaded datapoints together so the entry reloads only once."""
        datapoints = list(self.config_entry.data.get(CONF_DATAPOINTS, []))
        existing_ids = {datapoint["Id"] for datapoint in datapoints}
        for candidate, _data in self._candidates:
            if candidate["Id"] not in existing_ids:
                datapoints.append(candidate)
                existing_ids.add(candidate["Id"])
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, CONF_DATAPOINTS: datapoints},
        )

    async def async_step_remove(self, user_input=None):
        datapoints = self.config_entry.data.get(CONF_DATAPOINTS, [])
        if not datapoints:
            return self.async_abort(reason="no_datapoints")
        choices = {dp["Id"]: f'{dp["Id"]} — {dp["Name"]}' for dp in datapoints}
        if user_input is not None:
            remove_id = user_input[CONF_DATAPOINT_ID]
            dp = next(dp for dp in datapoints if dp["Id"] == remove_id)
            registry = er.async_get(self.hass)
            entity_id = registry.async_get_entity_id(dp["DPDescr"]["HAType"].replace("binarysensor", "binary_sensor"), DOMAIN, _unique_id(self.config_entry, dp))
            if entity_id:
                registry.async_remove(entity_id)
            remaining = [item for item in datapoints if item["Id"] != remove_id]
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, CONF_DATAPOINTS: remaining}
            )
            coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
            if coordinator:
                coordinator.datapoints = remaining
                coordinator.async_set_updated_data({
                    key: value for key, value in (coordinator.data or {}).items() if key != remove_id
                })
            return self.async_create_entry(title="", data=dict(self.config_entry.options))
        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema({vol.Required(CONF_DATAPOINT_ID): vol.In(choices)}),
        )

    async def async_step_settings(self, user_input=None):
        if user_input is not None:
            options = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Required(CONF_SCANINTERVAL, default=self.config_entry.options.get(CONF_SCANINTERVAL, DEFAULT_SCANINTERVAL)): vol.All(vol.Coerce(int), vol.Range(min=10)),
                vol.Required(CONF_HTTPTIMEOUT, default=self.config_entry.options.get(CONF_HTTPTIMEOUT, DEFAULT_HTTPTIMEOUT)): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(CONF_HTTPRETRIES, default=self.config_entry.options.get(CONF_HTTPRETRIES, DEFAULT_HTTPRETRIES)): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }),
        )

    def _client(self) -> SiemensOzw672ApiClient:
        """Create a short-lived client for an on-demand browser session."""
        entry = self.config_entry
        return SiemensOzw672ApiClient(
            entry.data[CONF_HOST], entry.data.get(CONF_PROTOCOL, "http"),
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD],
            async_create_clientsession(self.hass),
            entry.options.get(CONF_HTTPTIMEOUT, DEFAULT_HTTPTIMEOUT),
            entry.options.get(CONF_HTTPRETRIES, DEFAULT_HTTPRETRIES),
        )
    async def _build_datapoint_index(self) -> dict[str, dict]:
        """Recursively scan the menu only while this Options Flow is open."""
        client = self._client()
        if not await client.async_get_sessionid():
            raise ConnectionError
        index: dict[str, dict] = {}
        pending = [""]
        visited: set[str] = set()
        while pending:
            node_id = pending.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            node = await client.async_get_menu_node(node_id)
            if node is None:
                continue
            for raw in node.get("DatapointItems", []):
                index[raw["Id"]] = raw
            pending.extend(
                item["Id"] for item in node.get("MenuItems", [])
                if item.get("Id") not in visited
            )
        return index

    async def _load_datapoint(self, raw: dict) -> tuple[dict, dict]:
        """Read data and metadata only for the picker selection."""
        client = self._client()
        if not await client.async_get_sessionid():
            raise ConnectionError
        data = await client.async_get_data([raw])
        if raw["Id"] not in data:
            raise ValueError(raw["Id"])
        descr = await client.async_get_data_descr([raw], data)
        if raw["Id"] not in descr:
            raise ValueError(raw["Id"])
        return {
            "Id": raw["Id"],
            "WriteAccess": raw.get("WriteAccess", "false"),
            "OpLine": raw.get("Text", {}).get("Id", raw["Id"]),
            "Name": raw.get("Text", {}).get("Long", raw["Id"]),
            "MenuItem": "",
            "DPDescr": descr[raw["Id"]]["Description"],
        }, data[raw["Id"]]


def _unique_id(entry, datapoint: dict) -> str:
    """Match the ID used by platform entities."""
    identifier = str(datapoint.get("OpLine", ""))
    if not identifier or identifier == "0":
        identifier = f'00{datapoint["Id"]}'
    return f"{entry.entry_id}_{identifier}"
