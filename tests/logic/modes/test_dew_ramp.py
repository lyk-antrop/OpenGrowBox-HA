"""
Tests for the DewRamp drying mode (linear dew point ramp, no stages).
"""
import pytest
from datetime import datetime, timedelta
from tests.logic.helpers import FakeDataStore, FakeEventManager
from custom_components.opengrowbox.OGBController.actions.DryingActions import DryingActions
from custom_components.opengrowbox.OGBController.data.OGBDataClasses.OGBData import OGBConf
from custom_components.opengrowbox.OGBController.utils.calcs import calc_humidity_from_dew_point


def _make(elapsed_hours: float, temp=20.0, hum=62.0, **overrides):
    drying = OGBConf(hass=None).drying
    drying["currentDryMode"] = "DewRamp"
    drying["mode_start_time"] = (datetime.now() - timedelta(hours=elapsed_hours)).isoformat()
    drying["modes"]["DewRamp"].update(overrides)
    data_store = FakeDataStore({
        "drying": drying,
        "tentData": {"temperature": temp, "humidity": hum},
    })
    actions = DryingActions(data_store, FakeEventManager(), "test_room")
    actions.emitted = []

    async def tracked(name, data=None, **kwargs):
        actions.emitted.append(name)

    actions.event_manager.emit = tracked
    return actions


def _config(actions):
    return actions.data_store.getDeep("drying.modes.DewRamp")


class TestDewRampTarget:
    def test_start(self):
        actions = _make(0)
        assert actions.get_dew_ramp_target(_config(actions)) == 12.5

    def test_midpoint(self):
        actions = _make(168)
        assert actions.get_dew_ramp_target(_config(actions)) == 12.0

    def test_end_and_holds_after(self):
        actions = _make(336)
        assert actions.get_dew_ramp_target(_config(actions)) == 11.5
        actions = _make(1000)
        assert actions.get_dew_ramp_target(_config(actions)) == 11.5

    def test_rounded_to_two_decimals(self):
        actions = _make(100)
        target = actions.get_dew_ramp_target(_config(actions))
        assert target == round(target, 2)
        assert 11.5 < target < 12.5

    def test_missing_start_time(self):
        actions = _make(0)
        actions.data_store.setDeep("drying.mode_start_time", None)
        assert actions.get_dew_ramp_target(_config(actions)) is None

    def test_missing_config_key(self):
        actions = _make(0)
        config = dict(_config(actions))
        del config["endDewPoint"]
        assert actions.get_dew_ramp_target(config) is None


class TestDewRampControl:
    @pytest.mark.asyncio
    async def test_on_target_no_actions(self):
        hum = calc_humidity_from_dew_point(20.0, 12.5)
        actions = _make(0, hum=hum)
        await actions.handle_DewRamp(_config(actions))
        assert actions.emitted == []
        assert actions.data_store.getDeep("drying.current_phase") == "DewRamp"

    @pytest.mark.asyncio
    async def test_too_humid_dehumidifies(self):
        actions = _make(0, hum=70.0)
        await actions.handle_DewRamp(_config(actions))
        assert "Increase Dehumidifier" in actions.emitted

    @pytest.mark.asyncio
    async def test_too_dry_humidifies(self):
        actions = _make(0, hum=52.0)
        await actions.handle_DewRamp(_config(actions))
        assert "Increase Humidifier" in actions.emitted

    @pytest.mark.asyncio
    async def test_target_tracks_ramp(self):
        # 62 % is on target at day 0, but too humid once the ramp has reached 11.5 °C dew point
        hum = calc_humidity_from_dew_point(20.0, 12.5)
        start = _make(0, hum=hum)
        await start.handle_DewRamp(_config(start))
        assert start.emitted == []

        end = _make(336, hum=hum)
        await end.handle_DewRamp(_config(end))
        assert "Increase Dehumidifier" in end.emitted

    @pytest.mark.asyncio
    async def test_within_dew_point_tolerance_no_actions(self):
        # 63 % at 20 °C is ~12.7 °C dew point, 0.2 °C above the 12.5 °C target
        actions = _make(0, hum=63.0)
        await actions.handle_DewRamp(_config(actions))
        assert actions.emitted == []

    @pytest.mark.asyncio
    async def test_outside_dew_point_tolerance_dehumidifies(self):
        # 64 % is ~13 °C dew point, 1 °C above a 12 °C target, inside the 50-65 % RH limits
        actions = _make(0, hum=64.0, startDewPoint=12.0, endDewPoint=12.0)
        await actions.handle_DewRamp(_config(actions))
        assert "Increase Dehumidifier" in actions.emitted

    @pytest.mark.asyncio
    async def test_sensor_dew_point_preferred(self):
        actions = _make(0, hum=62.0)
        actions.data_store.setDeep("tentData.dewpoint", 15.0)
        await actions.handle_DewRamp(_config(actions))
        assert "Increase Dehumidifier" in actions.emitted

    @pytest.mark.asyncio
    async def test_min_humidity_overrides_dew_point(self):
        # Dew point (~8.7 °C) is above the 5 °C target, but RH is below the 50 % floor
        actions = _make(0, hum=48.0, startDewPoint=5.0, endDewPoint=5.0)
        await actions.handle_DewRamp(_config(actions))
        assert "Increase Humidifier" in actions.emitted
        assert "Increase Dehumidifier" not in actions.emitted

    @pytest.mark.asyncio
    async def test_max_humidity_overrides_dew_point(self):
        # Dew point (~13.6 °C) is below the 18 °C target, but RH is above the 65 % ceiling
        actions = _make(0, hum=66.0, startDewPoint=18.0, endDewPoint=18.0)
        await actions.handle_DewRamp(_config(actions))
        assert "Increase Dehumidifier" in actions.emitted
        assert "Increase Humidifier" not in actions.emitted

    @pytest.mark.asyncio
    async def test_temperature_control(self):
        hum = calc_humidity_from_dew_point(18.0, 12.5)
        actions = _make(0, temp=18.0, hum=hum)
        await actions.handle_DewRamp(_config(actions))
        assert "Increase Heater" in actions.emitted

    @pytest.mark.asyncio
    async def test_missing_sensor_data_skips(self):
        actions = _make(0)
        actions.data_store.setDeep("tentData.humidity", None)
        await actions.handle_DewRamp(_config(actions))
        assert actions.emitted == []

    @pytest.mark.asyncio
    async def test_dispatch_from_handle_drying(self):
        actions = _make(0, hum=70.0)
        await actions.handle_drying()
        assert "Increase Dehumidifier" in actions.emitted
