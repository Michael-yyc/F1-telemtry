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


def test_telemetry_download_failure_is_recoverable(monkeypatch):
    import streamlit as st
    from f1_analyser.open_data import DataSourceError
    st.cache_resource.clear()
    calls = []
    original = data.lap_telemetry
    def interrupted(lap):
        calls.append(1)
        if len(calls) == 1:
            raise DataSourceError("OpenF1 is limiting downloads. Wait a minute, then retry this comparison.")
        return original(lap)
    monkeypatch.setattr(data, "lap_telemetry", interrupted)
    app = AppTest.from_file(str(APP)).run()
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert "limiting downloads" in app.error[0].value
    next(b for b in app.button if b.label == "Retry telemetry download").click().run(timeout=30)
    assert not app.exception
    assert not app.error
    assert app.metric[0].value == "+0.138 s"


def test_q1_provider_restriction_can_recover_to_offline_q3(monkeypatch):
    import json
    import requests
    import streamlit as st
    from f1_analyser import open_data
    st.cache_resource.clear()
    def blocked(*a, **k):
        response = requests.Response()
        response.status_code = 401
        response._content = json.dumps({"detail": "Live F1 session in progress. Global API access is restricted."}).encode()
        return response
    monkeypatch.setattr(open_data.requests, "get", blocked)
    monkeypatch.setattr(open_data.time, "sleep", lambda _: None)
    app = AppTest.from_file(str(APP)).run()
    app.button[0].click().run(timeout=30)
    next(s for s in app.selectbox if s.label == "Qualifying segment / session").select("Q1").run(timeout=30)
    assert not app.exception
    assert "live F1 session" in app.error[0].value
    assert "Offline examples" in app.info[0].value
    laps = next(s for s in app.selectbox if s.label == "Reference lap")
    assert all('132.516' not in label for label in laps.options)
    next(s for s in app.selectbox if s.label == "Qualifying segment / session").select("Q3").run(timeout=30)
    assert not app.exception
    assert not app.error
    assert app.metric[0].value == "+0.138 s"
