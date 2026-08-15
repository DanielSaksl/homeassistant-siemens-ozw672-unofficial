"""Tests for the manual datapoint-management options flow."""
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.siemens_ozw672.const import (
    CONF_DATAPOINTS,
    CONF_HOST,
    CONF_HTTPRETRIES,
    CONF_HTTPTIMEOUT,
    CONF_PASSWORD,
    CONF_SCANINTERVAL,
    CONF_USERNAME,
    DOMAIN,
)


def _add_entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_options_entry",
        data={
            CONF_HOST: "gateway.local",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "password",
            CONF_DATAPOINTS: [],
        },
        options={CONF_SCANINTERVAL: 120},
    )
    entry.add_to_hass(hass)
    return entry


async def test_options_flow_opens_manual_manager(hass):
    entry = _add_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"
    assert result["menu_options"] == ["browser", "remove", "settings"]


async def test_options_flow_saves_polling_changes(hass):
    entry = _add_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "settings"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCANINTERVAL: 300,
            CONF_HTTPTIMEOUT: 10,
            CONF_HTTPRETRIES: 3,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SCANINTERVAL] == 300
