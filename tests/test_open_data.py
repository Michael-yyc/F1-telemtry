import numpy as np
import pandas as pd
import pytest

from f1_analyser.analysis import DataQualityError
from f1_analyser import open_data


def raw_car():
    start = pd.Timestamp("2023-03-04T16:00:00Z")
    return start, [dict(date=(start + pd.Timedelta(t, unit="s")).isoformat(),
                        speed=180, throttle=104, brake=100 if 5 <= t < 8 else 0, n_gear=7)
                   for t in np.arange(-.2, 20.3, .2)]


def test_boundary_interpolation_and_unit_mapping():
    start, raw = raw_car()
    frame = open_data.convert_car_data(raw, start, 20)
    assert frame.Time.iloc[0] == 0
    assert frame.Time.iloc[-1] == 20
    assert frame.Distance.iloc[-1] == pytest.approx(1000)
    assert set(frame.Brake) == {0, 1}
    assert frame.Throttle.max() == 100
    assert frame.nGear.eq(7).all()


@pytest.mark.parametrize("issue", ["gap", "unordered", "boundary", "brake"])
def test_rejects_unreliable_open_data(issue):
    start, raw = raw_car()
    if issue == "gap":
        raw = raw[:20] + raw[30:]
    elif issue == "unordered":
        raw[10], raw[11] = raw[11], raw[10]
    elif issue == "boundary":
        raw = raw[4:]
    else:
        raw[2]["brake"] = 50
    with pytest.raises(DataQualityError):
        open_data.convert_car_data(raw, start, 20)


def test_actual_open_query_filters_use_one_equals(monkeypatch):
    seen = {}
    start, raw = raw_car()
    def query(endpoint, **params):
        seen.update(params)
        return raw
    monkeypatch.setattr(open_data, "query", query)
    lap = pd.Series(dict(DateStart=start.isoformat(), SessionKey=7768, DriverNumber=1, LapTime=pd.Timedelta(20, unit="s")))
    open_data.open_lap_telemetry(lap)
    assert "date>" in seen and "date<" in seen
    assert "date>=" not in seen


def test_http_failure_is_not_empty_data(monkeypatch, tmp_path):
    class Forbidden:
        status_code = 403
        def raise_for_status(self):
            raise open_data.requests.HTTPError("Forbidden")
    monkeypatch.setattr(open_data, "BUNDLED", tmp_path / 'bundle')
    monkeypatch.setattr(open_data, "CACHE", tmp_path / 'cache')
    monkeypatch.setattr(open_data.requests, "get", lambda *a, **k: Forbidden())
    with pytest.raises(open_data.DataSourceError, match="refused"):
        open_data.query("pit", session_key=1)


@pytest.mark.parametrize("status,retry_after,calls", [(429, "0", 2), (503, "0", 2), (403, "0", 1), (429, "90", 1)])
def test_download_retries_only_transient_short_waits(monkeypatch, status, retry_after, calls):
    requests = []
    def get(*a, **k):
        response = open_data.requests.Response()
        response.status_code = status if not requests else 200
        response.headers["Retry-After"] = retry_after
        response.url = "https://api.openf1.org/v1/car_data"
        response._content = b'[{"speed": 180}]'
        requests.append(response)
        return response
    monkeypatch.setattr(open_data.requests, "get", get)
    monkeypatch.setattr(open_data.time, "sleep", lambda _: None)
    if calls == 2:
        assert open_data._download("car_data", {})[0] == [{"speed": 180}]
    else:
        with pytest.raises(open_data.DataSourceError):
            open_data._download("car_data", {})
    assert len(requests) == calls


def test_timeout_is_bounded_and_does_not_leak_request_details(monkeypatch):
    calls = []
    def get(*a, **k):
        calls.append(1)
        raise open_data.requests.Timeout("private request diagnostic")
    monkeypatch.setattr(open_data.requests, "get", get)
    monkeypatch.setattr(open_data.time, "sleep", lambda _: None)
    with pytest.raises(open_data.DataSourceError, match="Could not connect") as error:
        open_data._download("car_data", {})
    assert "private" not in str(error.value)
    assert len(calls) == 2


def test_q1_slow_laps_in_screenshot_are_excluded():
    session = open_data.load_open_session(2023, "Bahrain", "Q")
    laps = session.laps[(session.laps.Segment == "Q1") & session.laps.Driver.isin(["VER", "PER"])]
    assert set(laps.LapNumber) == {3}
    assert laps.LapTime.dt.total_seconds().max() < 92


def test_live_session_restriction_is_explained_without_retry(monkeypatch):
    import json
    calls = []
    def get(*a, **k):
        calls.append(1)
        response = open_data.requests.Response()
        response.status_code = 401
        response._content = json.dumps({"detail": "Live F1 session in progress. Global API access (including past sessions) is restricted to authenticated users until the session ends."}).encode()
        return response
    monkeypatch.setattr(open_data.requests, "get", get)
    monkeypatch.setattr(open_data.time, "sleep", lambda _: None)
    with pytest.raises(open_data.DataSourceError, match="while a live F1 session is in progress"):
        open_data._download("car_data", {})
    assert len(calls) == 1


def test_offline_availability_hint_matches_real_bundle():
    session = open_data.load_open_session(2023, "Bahrain", "Q")
    laps = session.laps[session.laps.Driver == "VER"]
    assert open_data.bundled_telemetry(laps[laps.Segment == "Q3"].sort_values('LapTime').iloc[0])
    assert not open_data.bundled_telemetry(laps[laps.Segment == "Q1"].sort_values('LapTime').iloc[0])


@pytest.mark.parametrize("event,recorded", [("Bahrain", .138), ("Monza", .381), ("Abu Dhabi", .726)])
def test_real_snapshots_work_without_network(monkeypatch, event, recorded):
    from f1_analyser.data import load_session, fastest_pair, lap_telemetry
    from f1_analyser.analysis import compare_laps
    def no_network(*a, **k):
        pytest.fail("Bundled comparison unexpectedly requested network access")
    monkeypatch.setattr(open_data.requests, "get", no_network)
    session = load_session(2023, event, "Q")
    a, b = fastest_pair(session, "VER", "PER")
    ta, tb = lap_telemetry(a), lap_telemetry(b)
    result = compare_laps(ta, tb, a.LapTime.total_seconds(), b.LapTime.total_seconds())
    assert result.recorded_gap == pytest.approx(recorded)
    assert result.coverage > .99
    assert compare_laps(ta, ta, a.LapTime.total_seconds(), a.LapTime.total_seconds()).estimated_gap == 0
    assert compare_laps(tb, ta, b.LapTime.total_seconds(), a.LapTime.total_seconds()).estimated_gap == pytest.approx(-result.estimated_gap)


def test_deleted_lap_is_matched_by_time_not_offset_number():
    session = open_data.load_open_session(2023, "Abu Dhabi", "Q")
    # RCM identifies LAP 17, but OpenF1 numbers the 1:23.868 lap as 16.
    per = session.laps[session.laps.Driver == "PER"]
    assert 16 not in set(per.LapNumber)
    assert not per.LapTime.eq(pd.Timedelta(83.868, unit="s")).any()


def test_snapshot_integrity_check(monkeypatch, tmp_path):
    import json
    import hashlib
    key = hashlib.sha256(json.dumps(["pit", {"session_key": 1}], sort_keys=True).encode()).hexdigest()
    (tmp_path / f"{key}.json").write_text('{}')
    (tmp_path / "manifest.json").write_text(json.dumps({"files": [{"file": f"{key}.json", "sha256": "wrong"}]}))
    monkeypatch.setattr(open_data, "BUNDLED", tmp_path)
    with pytest.raises(DataQualityError, match="integrity"):
        open_data.query("pit", session_key=1)
