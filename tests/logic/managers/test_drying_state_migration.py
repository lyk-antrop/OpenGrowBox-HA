from custom_components.opengrowbox.OGBController.data.OGBDataClasses.OGBData import OGBConf
from custom_components.opengrowbox.OGBController.managers.OGBDSManager import (
    _merge_drying_modes,
)


def _defaults():
    return OGBConf(hass=None).drying


def _legacy_saved_drying():
    """A drying block saved before DewRamp existed."""
    drying = _defaults()
    del drying["modes"]["DewRamp"]
    drying["currentDryMode"] = "ElClassico"
    drying["mode_start_time"] = "2026-10-09T08:00:00"
    drying["modes"]["ElClassico"]["phase"]["start"]["targetHumidity"] = 63
    return drying


def test_missing_mode_is_added_from_defaults():
    merged = _merge_drying_modes(_legacy_saved_drying(), _defaults())

    assert merged["modes"]["DewRamp"]["startDewPoint"] == 12.5
    assert merged["modes"]["DewRamp"]["totalDurationHours"] == 336


def test_removed_mode_is_deleted():
    saved = _legacy_saved_drying()
    saved["modes"]["OldMode"] = {"isActive": True}

    merged = _merge_drying_modes(saved, _defaults())

    assert "OldMode" not in merged["modes"]
    assert set(merged["modes"]) == set(_defaults()["modes"])


def test_keys_inside_an_existing_mode_are_left_alone():
    saved = _legacy_saved_drying()
    del saved["modes"]["ElClassico"]["phase"]["halfTime"]
    saved["modes"]["ElClassico"]["customKey"] = 1

    merged = _merge_drying_modes(saved, _defaults())

    assert "halfTime" not in merged["modes"]["ElClassico"]["phase"]
    assert merged["modes"]["ElClassico"]["customKey"] == 1


def test_saved_values_are_kept():
    merged = _merge_drying_modes(_legacy_saved_drying(), _defaults())

    assert merged["currentDryMode"] == "ElClassico"
    assert merged["mode_start_time"] == "2026-10-09T08:00:00"
    assert merged["modes"]["ElClassico"]["phase"]["start"]["targetHumidity"] == 63


def test_saved_setting_value_is_not_overwritten():
    saved = _legacy_saved_drying()
    saved["modes"]["DewRamp"] = dict(_defaults()["modes"]["DewRamp"], startDewPoint=13.0)

    merged = _merge_drying_modes(saved, _defaults())

    assert merged["modes"]["DewRamp"]["startDewPoint"] == 13.0
    assert merged["modes"]["DewRamp"]["endDewPoint"] == 11.5


def test_defaults_are_copied_not_shared():
    defaults = _defaults()
    merged = _merge_drying_modes(_legacy_saved_drying(), defaults)

    merged["modes"]["DewRamp"]["startDewPoint"] = 99

    assert defaults["modes"]["DewRamp"]["startDewPoint"] == 12.5


def test_non_dict_values_are_returned_unchanged():
    assert _merge_drying_modes(None, {"modes": {}}) is None
    assert _merge_drying_modes({"a": 1}, None) == {"a": 1}
