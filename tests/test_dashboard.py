from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

import f1_analyser.data as data


APP = Path(__file__).resolve().parents[1] / "app.py"


def test_dashboard_initial_state():
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert app.title[0].value == "F1 · Lap Lab"
    assert "Load session" in app.info[0].value


def test_dashboard_provider_failure_is_visible(monkeypatch):
    def unavailable(*args):
        raise ConnectionError("Data provider unavailable")
    monkeypatch.setattr(data, "load_session", unavailable)
    app = AppTest.from_file(str(APP)).run()
    app.button[0].click().run()
    assert not app.exception
    assert "Data provider unavailable" in app.error[0].value


def test_dashboard_full_comparison_with_controlled_fixture(monkeypatch):
    # Synthetic integration fixture, never presented as historical telemetry.
    rows = []
    for driver, duration in (("VER", 20.0), ("PER", 22.5)):
        rows.append(dict(Driver=driver, LapNumber=1, LapTime=pd.Timedelta(duration, unit="s"),
                         Segment="Q3", Compound="SOFT", TyreLife=3.0, FreshTyre=True,
                         Sector1Time=pd.Timedelta(6, unit="s"), Sector2Time=pd.Timedelta(7, unit="s"),
                         Sector3Time=pd.Timedelta(duration - 13, unit="s")))
    laps = pd.DataFrame(rows)
    session = SimpleNamespace(event={"EventName": "Synthetic test fixture"}, name="Qualifying")
    monkeypatch.setattr(data, "load_session", lambda *args: session)
    monkeypatch.setattr(data, "eligible_laps", lambda _: laps)

    def telemetry(lap):
        distance = np.linspace(0, 1000, 101)
        return pd.DataFrame(dict(Distance=distance, Time=distance / 1000 * lap.LapTime.total_seconds(),
                                 Speed=1000 / lap.LapTime.total_seconds() * 3.6,
                                 Throttle=np.where((distance > 200) & (distance < 400), 0, 100),
                                 Brake=(distance > 200) & (distance < 300), nGear=7))
    monkeypatch.setattr(data, "lap_telemetry", telemetry)
    app = AppTest.from_file(str(APP)).run()
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert not app.error
    assert app.metric[0].value == "+2.500 s"
    assert app.metric[2].value == "+0.000 s"
    assert len(app.dataframe) == 2


def test_dashboard_with_real_bahrain_snapshot():
    import streamlit as st
    st.cache_resource.clear()
    app = AppTest.from_file(str(APP)).run()
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert not app.error
    assert app.metric[0].value == "+0.138 s"
    assert app.metric[1].value == "+0.087 s"
    assert len(app.dataframe) == 4
