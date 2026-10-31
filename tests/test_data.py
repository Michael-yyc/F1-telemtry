from types import SimpleNamespace

import fastf1
import pandas as pd
import pytest

from f1_analyser.analysis import DataQualityError
from f1_analyser.data import eligible_laps, fastest_pair


def session_fixture(monkeypatch):
    rows = []
    for index, driver in enumerate(["VER", "PER", "VER", "PER", "VER", "PER", "VER", "PER"]):
        rows.append(dict(Driver=driver, LapNumber=index + 1,
                         LapTime=pd.Timedelta(90 + index, unit="s"),
                         PitInTime=pd.NaT, PitOutTime=pd.NaT, IsAccurate=True,
                         Deleted=False, TrackStatus="1", Compound="SOFT"))
    laps = fastf1.core.Laps(pd.DataFrame(rows))
    for field in ("PitInTime", "PitOutTime"):
        laps[field] = pd.Series(pd.NaT, index=laps.index, dtype="timedelta64[ns]")
    # Q1's quicker laps must never be selected when Q3 is requested.
    monkeypatch.setattr(fastf1.core.Laps, "split_qualifying_sessions", lambda self: [self.iloc[:2], self.iloc[2:4], self.iloc[4:]])
    return SimpleNamespace(laps=laps, name="Qualifying")


def test_fastest_pair_respects_segment_and_common_compound(monkeypatch):
    session = session_fixture(monkeypatch)
    session.laps.loc[4, "Compound"] = "MEDIUM"
    a, b = fastest_pair(session, "VER", "PER")
    assert a.LapNumber == 7
    assert b.LapNumber == 6
    assert a.Compound == b.Compound == "SOFT"


@pytest.mark.parametrize("field,value", [("Deleted", True), ("IsAccurate", False),
    ("Deleted", None), ("PitInTime", pd.Timedelta(1, unit="s")),
    ("PitOutTime", pd.Timedelta(1, unit="s")), ("TrackStatus", "12"), ("Compound", "INTERMEDIATE"),
    ("LapTime", pd.NaT)])
def test_unsuitable_laps_are_excluded(monkeypatch, field, value):
    session = session_fixture(monkeypatch)
    if value is None:
        session.laps[field] = session.laps[field].astype(object)
    session.laps.loc[4, field] = value
    assert 4 not in eligible_laps(session).index


def test_pair_without_common_compound_is_rejected(monkeypatch):
    session = session_fixture(monkeypatch)
    session.laps.loc[session.laps.Driver == "VER", "Compound"] = "HARD"
    with pytest.raises(DataQualityError, match="common tyre"):
        fastest_pair(session, "VER", "PER")
