from datetime import datetime, timedelta, timezone

import pytest

from tests.logic.helpers import FakeDataStore, FakeEventManager
from tests.logic.managers.test_configuration_manager_day_night import (
    OGBConfigurationManager,
    _event_pub,
)


def _make(start=None):
    return OGBConfigurationManager(
        data_store=FakeDataStore({"drying": {"mode_start_time": start}}),
        event_manager=FakeEventManager(),
        room="dev_room",
        hass=None,
    )


def _saved(mgr):
    return [e for e in mgr.event_manager.emitted if e["event_name"] == "SaveState"]


@pytest.mark.asyncio
async def test_entity_update_is_routed_to_handler():
    mgr = _make()
    assert mgr.handle_configuration_update(
        "datetime.ogb_dryingstart_dev_room", _event_pub("2026-10-09T06:00:00+00:00")
    )


@pytest.mark.asyncio
async def test_sets_naive_local_start_and_saves():
    mgr = _make(start=datetime.now().isoformat())
    aware = datetime(2026, 10, 9, 6, 0, tzinfo=timezone.utc)

    await mgr._update_drying_start(_event_pub(aware.isoformat()))

    expected = aware.astimezone().replace(tzinfo=None)
    assert mgr.data_store.getDeep("drying.mode_start_time") == expected.isoformat()
    assert len(_saved(mgr)) == 1


@pytest.mark.asyncio
async def test_unchanged_value_is_ignored():
    start = datetime(2026, 10, 9, 8, 0, 0, 400000)
    mgr = _make(start=start.isoformat())
    same = start.astimezone().replace(microsecond=0)

    await mgr._update_drying_start(_event_pub(same.isoformat()))

    assert mgr.data_store.getDeep("drying.mode_start_time") == start.isoformat()
    assert _saved(mgr) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["unknown", "unavailable", "", None, "not a date"])
async def test_unavailable_or_invalid_value_is_ignored(value):
    original = (datetime.now() - timedelta(days=2)).isoformat()
    mgr = _make(start=original)

    await mgr._update_drying_start(_event_pub(value))

    assert mgr.data_store.getDeep("drying.mode_start_time") == original
    assert _saved(mgr) == []
