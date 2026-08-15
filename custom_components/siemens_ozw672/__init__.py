"""Siemens OZW672 integration setup and polling coordinator."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SiemensOzw672ApiClient
from .const import (
    CONF_DATAPOINTS, CONF_HOST, CONF_HTTPRETRIES, CONF_HTTPTIMEOUT,
    CONF_PASSWORD, CONF_PROTOCOL, CONF_SCANINTERVAL, CONF_USERNAME,
    DEFAULT_HTTPRETRIES, DEFAULT_HTTPTIMEOUT, DEFAULT_SCANINTERVAL, DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config) -> bool:
    """YAML configuration is not supported."""
    _async_repair_string_entry_versions(hass)
    return True


def _async_repair_string_entry_versions(hass: HomeAssistant) -> None:
    """Repair the string config-entry versions written by releases 0.3.6/0.3.7."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if isinstance(entry.version, int) and isinstance(entry.minor_version, int):
            continue
        try:
            version = int(entry.version)
            minor_version = int(entry.minor_version)
        except (TypeError, ValueError):
            _LOGGER.error(
                "Config entry %s has an unparseable version (%r.%r) and cannot be "
                "repaired automatically; please remove and re-add the integration",
                entry.entry_id, entry.version, entry.minor_version,
            )
            continue
        _LOGGER.warning("Repairing string version for config entry %s", entry.entry_id)
        hass.config_entries.async_update_entry(
            entry, version=version, minor_version=minor_version
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the gateway and only the datapoints explicitly stored in the entry."""
    hass.data.setdefault(DOMAIN, {})
    timeout = entry.options.get(CONF_HTTPTIMEOUT, DEFAULT_HTTPTIMEOUT)
    retries = entry.options.get(CONF_HTTPRETRIES, DEFAULT_HTTPRETRIES)
    datapoints = entry.data.get(CONF_DATAPOINTS, [])
    client = SiemensOzw672ApiClient(
        entry.data[CONF_HOST], entry.data.get(CONF_PROTOCOL, "http"),
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD],
        async_get_clientsession(hass), timeout=timeout, retries=retries,
    )
    try:
        if not await client.async_get_sessionid():
            raise ConfigEntryNotReady("Authentication to OZW672 failed")
    except Exception as err:
        raise ConfigEntryNotReady("Cannot connect to OZW672") from err

    coordinator = SiemensOzw672DataUpdateCoordinator(
        hass, client, datapoints,
        timedelta(seconds=entry.options.get(CONF_SCANINTERVAL, DEFAULT_SCANINTERVAL)),
    )
    # An empty manual list is a successful setup and must not initiate any reads.
    if datapoints:
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            raise ConfigEntryNotReady
    else:
        coordinator.async_set_updated_data({})

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Keep existing selected datapoints, while making old entries manual-ready."""
    if entry.version != 1 or entry.minor_version < 6:
        data = dict(entry.data)
        data.setdefault(CONF_DATAPOINTS, [])
        data.setdefault("devicename", data.get(CONF_HOST, "OZW672"))
        data.setdefault("prefix_with_function", False)
        data.setdefault("prefix_with_opline", False)
        hass.config_entries.async_update_entry(entry, data=data, version=1, minor_version=6)
    return True


class SiemensOzw672DataUpdateCoordinator(DataUpdateCoordinator):
    """Poll only the datapoints selected by the user."""

    def __init__(self, hass, client, datapoints, scaninterval) -> None:
        self.api = client
        self.datapoints = datapoints
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=scaninterval)

    async def _async_update_data(self):
        try:
            return await self.api.async_get_data(self.datapoints)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with OZW672: {err}") from err

    async def _async_update_data_forid(self, datapoint_id):
        datapoint = next(dp for dp in self.datapoints if dp["Id"] == datapoint_id)
        return await self.api.async_get_data([datapoint])


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply manual add/remove operations immediately, without HA restart."""
    await hass.config_entries.async_reload(entry.entry_id)
