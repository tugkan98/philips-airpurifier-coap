"""Regressions observed on AMF870/15 and AC3420/10 devices."""

from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.philips_airpurifier_coap import humidifier, number
from custom_components.philips_airpurifier_coap.config_entry_data import ConfigEntryData
from custom_components.philips_airpurifier_coap.const import DOMAIN, PhilipsApi
from custom_components.philips_airpurifier_coap.light import PhilipsLight
from custom_components.philips_airpurifier_coap.model import DeviceInformation
from custom_components.philips_airpurifier_coap.select import PhilipsSelect
from custom_components.philips_airpurifier_coap.sensor import PhilipsSensor
from custom_components.philips_airpurifier_coap.switch import PhilipsSwitch


@pytest.fixture
def device(hass):
    """Build entities using a mocked transport and an actual config entry."""

    def create(model="AMF870", **status):
        state = {
            PhilipsApi.MODEL_ID: model,
            PhilipsApi.DEVICE_ID: "test-device",
            PhilipsApi.WIFI_VERSION: "test-firmware",
            PhilipsApi.NEW2_GAS: 1,
            PhilipsApi.NEW2_POWER: 0,
            PhilipsApi.NEW2_DISPLAY_BACKLIGHT: 100,
            PhilipsApi.AMF870_DISPLAY_BACKLIGHT: 20,
            "D03128": 60,
            **status,
        }
        client = Mock(set_control_value=AsyncMock(return_value=True))
        coordinator = Mock(status=state, client=client)
        data = ConfigEntryData(
            DeviceInformation(model, "Test device", "test-device", "device.invalid"),
            client,
            coordinator,
            state,
        )
        entry = MockConfigEntry(domain=DOMAIN, data={})
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
        return entry, data

    return create


async def test_amf_display_uses_physical_field_and_preserves_unique_id(hass, device):
    """The ineffective echoed field must never be used for AMF870 display writes."""
    entry, data = device()
    light = PhilipsLight(hass, entry, data, PhilipsApi.NEW2_DISPLAY_BACKLIGHT)
    light._handle_coordinator_update = Mock()
    assert light.brightness == 51
    assert light.unique_id == "AMF870-test-device-d0312d"
    await light.async_turn_on(brightness=178)
    data.client.set_control_value.assert_awaited_once_with("D0312F", 70)
    assert data.coordinator.status["D0312D"] == 100
    await light.async_turn_off()
    data.client.set_control_value.assert_awaited_with("D0312F", 0)
    assert not light.is_on


def test_amf765_keeps_original_display_field(hass, device):
    """Do not assume an untested sibling uses the AMF870 display field."""
    entry, data = device("AMF765")
    light = PhilipsLight(hass, entry, data, PhilipsApi.NEW2_DISPLAY_BACKLIGHT)
    assert light.kind == "D0312D"
    assert light.brightness == 255


@pytest.mark.parametrize("value", [1, 2, 3, 4, 0, 5, None, True, "2", 2.5])
def test_gas_levels_are_categories(hass, device, value):
    """L1-L4 are levels, not numeric measurements in liters."""
    entry, data = device(D03122=value)
    sensor = PhilipsSensor(hass, entry, data, PhilipsApi.NEW2_GAS)
    expected = f"L{value}" if type(value) is int and 1 <= value <= 4 else None
    assert sensor.native_value == expected
    assert sensor.device_class == SensorDeviceClass.ENUM
    assert sensor.options == ["L1", "L2", "L3", "L4"]
    assert sensor.state_class is None
    assert sensor.native_unit_of_measurement is None
    assert sensor.translation_key == "gas_level"
    assert sensor.unique_id == "AMF870-test-device-d03122"


def test_other_sensor_descriptions_are_not_mutated(hass, device):
    """The per-model gas conversion must not alter shared descriptions."""
    entry, data = device("AC3737")
    sensor = PhilipsSensor(hass, entry, data, PhilipsApi.NEW2_GAS)
    assert sensor.native_value == 1
    assert sensor.native_unit_of_measurement == "L"


@pytest.mark.parametrize("model, expected", [("AC3420", 1), ("AC3421", 0)])
async def test_target_humidity_is_scoped_to_ac3420(hass, device, model, expected):
    """Keep the inherited AC3421 platform unchanged."""
    entry, _ = device(model)
    entities = []
    await number.async_setup_entry(hass, entry, lambda added, **kwargs: entities.extend(added))
    assert len(entities) == expected
    if expected:
        target = entities[0]
        assert target.translation_key == "target_humidity"
        assert target.entity_category is None
        assert (target.native_min_value, target.native_max_value, target.native_step) == (40, 70, 10)
        assert target.native_unit_of_measurement == "%"
        assert target.icon == "mdi:water-percent"


@pytest.mark.parametrize("power", [0, 1])
async def test_target_humidity_writes_do_not_toggle_power(hass, device, power):
    """A target-only control must only write D03128."""
    entry, data = device("AC3420", D03102=power)
    target = number.PhilipsNumber(hass, entry, data, "D03128")
    target._handle_coordinator_update = Mock()
    await target.async_set_native_value(50)
    data.client.set_control_value.assert_awaited_once_with("D03128", 50)
    assert data.coordinator.status["D03102"] == power
    data.coordinator.status["D03128"] = 70
    assert target.native_value == 70


@pytest.mark.parametrize("model, enabled", [("AC3420", False), ("AC3421", True)])
async def test_legacy_humidifier_remains_available_for_existing_automations(hass, device, model, enabled):
    """Only new AC3420 registrations omit the duplicate control by default."""
    entry, _ = device(model)
    entities = []
    await humidifier.async_setup_entry(hass, entry, lambda added, **kwargs: entities.extend(added))
    assert len(entities) == 1
    assert entities[0].entity_registry_enabled_default is enabled
    assert entities[0].unique_id == f"{model}-test-device-d03128#1"


def test_amf_categories_keep_timer_in_configuration(hass, device):
    """Separate daily controls from device preferences without moving Timer."""
    entry, data = device()
    for key in (PhilipsApi.NEW2_OSCILLATION, PhilipsApi.NEW2_TARGET_TEMP):
        assert number.PhilipsNumber(hass, entry, data, key).entity_category is None
    assert PhilipsSelect(hass, entry, data, PhilipsApi.NEW2_HEATING).entity_category is None
    assert PhilipsSelect(hass, entry, data, PhilipsApi.NEW2_TIMER).entity_category == EntityCategory.CONFIG
    for key in (PhilipsApi.NEW2_AUTO_PLUS_AI, PhilipsApi.NEW2_STANDBY_SENSORS):
        assert PhilipsSwitch(hass, entry, data, key).entity_category == EntityCategory.CONFIG
