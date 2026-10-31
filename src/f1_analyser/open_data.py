"""OpenF1 historical data adapter. No account or subscription is required.

Responses are cached verbatim; attribution and query hashes travel with snapshots.
OpenF1: https://openf1.org/, CC BY-NC-SA 4.0 (noncommercial use).
"""
import hashlib
import json
import re
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import requests

from .analysis import DataQualityError, prepare_telemetry

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache" / "openf1"
BUNDLED = ROOT / "datasets" / "openf1"
BASE = "https://api.openf1.org/v1/"
_lock = threading.Lock()
_last_request = 0.0


class DataSourceError(RuntimeError):
    """A remote provider could not supply the requested data."""


def _download(endpoint, params):
    global _last_request
    for attempt in range(2):
        try:
            with _lock:
                delay = 2.1 - (time.monotonic() - _last_request)
                if delay > 0:
                    time.sleep(delay)
                _last_request = time.monotonic()
                response = requests.get(BASE + endpoint, params=params, timeout=30)
            if response.status_code in (429, 502, 503, 504) and attempt == 0:
                retry_after = getattr(response, "headers", {}).get("Retry-After", "2.1")
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = 2.1
                # Respect longer server waits by returning control to the user.
                if 0 <= delay <= 5:
                    time.sleep(delay)
                    continue
            if response.status_code == 404 and response.json() == {"detail": "No results found."}:
                return [], response.url
            response.raise_for_status()
            return response.json(), response.url
        except requests.HTTPError as exc:
            status = response.status_code
            detail = ""
            if status == 401:
                try:
                    payload = response.json()
                    detail = payload.get("detail", "") if isinstance(payload, dict) else ""
                except ValueError:
                    pass
            if isinstance(detail, str) and detail.startswith("Live F1 session in progress."):
                message = ("OpenF1 temporarily restricts all API downloads, including historical sessions, "
                           "while a live F1 session is in progress. Use a bundled comparison now, "
                           "or retry after the live session ends.")
            elif status == 429:
                message = "OpenF1 is limiting downloads. Wait a minute, then retry this comparison."
            elif status in (401, 403):
                message = "OpenF1 refused this download. Try another lap or the bundled Bahrain Q3 VER/PER comparison."
            else:
                message = f"OpenF1 could not supply this download (HTTP {status}). Try again later or choose another lap."
            raise DataSourceError(message) from exc
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == 0:
                continue
            raise DataSourceError("Could not connect to OpenF1. Retry later or use the bundled Bahrain Q3 VER/PER comparison.") from exc
        except requests.RequestException as exc:
            raise DataSourceError("OpenF1 returned an unreadable response. Retry later or choose another lap.") from exc


def query(endpoint, **params):
    """Prefer reproducible bundled responses, then cache, then rate-limited HTTPS."""
    key = hashlib.sha256(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()
    for directory in (BUNDLED, CACHE):
        path = directory / f"{key}.json"
        if path.exists():
            if directory == BUNDLED:
                manifest = json.loads((BUNDLED / "manifest.json").read_text())
                expected = {item["file"]: item["sha256"] for item in manifest["files"]}
                if expected.get(path.name) != hashlib.sha256(path.read_bytes()).hexdigest():
                    raise DataQualityError("Bundled OpenF1 response failed its SHA-256 integrity check.")
            payload = json.loads(path.read_text())
            if payload["endpoint"] != endpoint or payload["params"] != params:
                raise DataQualityError("OpenF1 cache query mismatch.")
            return payload["data"]
    data, url = _download(endpoint, params)
    if not isinstance(data, list):
        raise DataQualityError("OpenF1 returned an unexpected response.")
    CACHE.mkdir(parents=True, exist_ok=True)
    payload = dict(endpoint=endpoint, params=params, data=data, source=url,
                   retrieved_utc=pd.Timestamp.now(tz="UTC").isoformat(),
                   licence="CC BY-NC-SA 4.0", attribution="OpenF1 contributors, https://openf1.org/")
    (CACHE / f"{key}.json").write_text(json.dumps(payload, indent=2) + "\n")
    return data


def session_laps(meta, raw, drivers, stints, controls, pits):
    """Conservative selection using timing, stints and available race-control records.

    This is not FastF1's IsAccurate flag. Deleted-lap exclusions are conservative:
    reinstated laps remain excluded. Phase comes from explicit qualifying_phase.
    """
    names = {d["driver_number"]: d["name_acronym"] for d in drivers}
    controls = sorted(controls, key=lambda m: m["date"])
    deleted = set()
    phases = {}
    for message in controls:
        text = message["message"]
        match = re.search(r"CAR\s+(\d+).*\bLAP\s+(\d+)", text)
        if "DELETED" in text and match:
            driver, number = map(int, match.groups())
            timing = re.search(r"\bTIME\s+(\d+):(\d+\.\d+)", text)
            if timing:
                # OpenF1 and race-control lap numbering can differ by one.
                # Match the reported driver + duration, not a guessed offset.
                seconds = 60 * int(timing[1]) + float(timing[2])
                deleted.update((driver, lap["lap_number"]) for lap in raw
                               if lap["driver_number"] == driver and lap.get("lap_duration")
                               and abs(lap["lap_duration"] - seconds) < .0015)
            else:
                # A message without duration is ambiguous: exclude both candidates.
                deleted.update({(driver, number), (driver, number - 1)})
        phase = message.get("qualifying_phase")
        if phase and message.get("flag") == "GREEN":
            phases.setdefault(int(phase), pd.Timestamp(message["date"]))
    rows = []
    for lap in raw:
        duration = lap.get("lap_duration")
        if not duration or not lap.get("date_start") or lap.get("is_pit_out_lap"):
            continue
        driver, number = lap["driver_number"], lap["lap_number"]
        sectors = [lap.get(f"duration_sector_{i}") for i in (1, 2, 3)]
        if any(x is None for x in sectors) or abs(sum(sectors) - duration) > .02:
            continue
        if (driver, number) in deleted or any(p["driver_number"] == driver and p["lap_number"] == number for p in pits):
            continue
        start = pd.Timestamp(lap["date_start"])
        end = start + pd.Timedelta(duration, unit="s")
        flags = [m for m in controls if m.get("flag") in ("YELLOW", "DOUBLE YELLOW", "RED")
                 and start <= pd.Timestamp(m["date"]) <= end]
        previous = [m for m in controls if m.get("scope") == "Track" and m.get("flag") in ("GREEN", "RED", "YELLOW", "DOUBLE YELLOW")
                    and pd.Timestamp(m["date"]) <= start]
        if flags or not previous or previous[-1]["flag"] != "GREEN":
            continue
        compound_stints = [s for s in stints if s["driver_number"] == driver
                           and s["lap_start"] <= number <= (s.get("lap_end") or 9999)]
        if not compound_stints:
            continue
        stint = compound_stints[-1]
        if stint["compound"] not in ("SOFT", "MEDIUM", "HARD"):
            continue
        phase = max((p for p, date in phases.items() if date <= start), default=0)
        if meta["session_type"] == "Qualifying" and not phase:
            continue
        age = stint.get("tyre_age_at_start")
        rows.append(dict(Driver=names.get(driver, str(driver)), DriverNumber=driver, LapNumber=number,
                         LapTime=pd.Timedelta(duration, unit="s"), Segment=f"Q{phase}" if phase else "Session",
                         Compound=stint["compound"], TyreLife=np.nan if age is None else age + number - stint["lap_start"],
                         FreshTyre=None, Sector1Time=pd.Timedelta(sectors[0], unit="s"),
                         Sector2Time=pd.Timedelta(sectors[1], unit="s"), Sector3Time=pd.Timedelta(sectors[2], unit="s"),
                         LapStartTime=start - pd.Timestamp(meta["date_start"]), DateStart=start.isoformat(),
                         SessionKey=meta["session_key"], Source="OpenF1"))
    result = pd.DataFrame(rows)
    if not result.empty and meta["session_type"] == "Qualifying":
        # Sector-complete cooldown/in laps may exist where pit records are absent.
        # This is a comparison heuristic, not the FIA's qualification rule.
        fastest = result.groupby(["Driver", "Segment"]).LapTime.transform("min")
        result = result[result.LapTime <= fastest * 1.07].copy()
    return result


def load_open_session(year, event, code="Q"):
    codes = {"Q": "Qualifying", "R": "Race", "FP1": "Practice 1", "FP2": "Practice 2", "FP3": "Practice 3", "S": "Sprint", "SQ": "Sprint Qualifying"}
    sessions = query("sessions", year=int(year), session_name=codes.get(code, code))
    needle = str(event).strip().casefold()
    aliases = {"abu dhabi": "yas marina circuit"}
    needle = aliases.get(needle, needle)
    matches = [s for s in sessions if any(needle == str(s.get(k, "")).casefold() for k in ("country_name", "location", "circuit_short_name", "session_key"))]
    if len(matches) != 1:
        raise DataQualityError("Specify an unambiguous country/circuit or OpenF1 session key (2023 onward).")
    meta = matches[0]
    key = meta["session_key"]
    rows = session_laps(meta, query("laps", session_key=key), query("drivers", session_key=key),
                        query("stints", session_key=key), query("race_control", session_key=key), query("pit", session_key=key))
    return SimpleNamespace(laps=rows, source="OpenF1", name=meta["session_name"],
                           event={"EventName": f"{meta['country_name']} · {meta['circuit_short_name']}"}, metadata=meta)


def convert_car_data(raw, start, duration):
    """Interpolate bracketed boundaries, then integrate speed to metres.

    Continuous throttle is clipped to the physical 0–100 range (OpenF1 notes
    occasional source values above 100). Binary brake is mapped from 0/100.
    """
    if not raw:
        raise DataQualityError("No OpenF1 telemetry samples returned.")
    frame = pd.DataFrame(raw)
    timestamps = pd.to_datetime(frame.date, utc=True, format="ISO8601")
    t = (timestamps - pd.Timestamp(start)).dt.total_seconds().to_numpy()
    if np.any(np.diff(t) <= 0):
        raise DataQualityError("OpenF1 telemetry timestamps are not ordered and unique.")
    if t[0] > 0 or t[-1] < duration or np.max(np.diff(t)) > 1.5:
        raise DataQualityError("Telemetry must bracket both lap boundaries without gaps above 1.5 s.")
    grid = np.r_[0.0, t[(t > 0) & (t < duration)], duration]
    out = pd.DataFrame({"Time": grid})
    for source, target in (("speed", "Speed"), ("throttle", "Throttle")):
        values = frame[source].to_numpy(dtype=float)
        if target == "Throttle":
            values = np.clip(values, 0, 100)
        out[target] = np.interp(grid, t, values)
    if not frame.brake.isin([0, 100]).all():
        raise DataQualityError("Unexpected OpenF1 brake state; expected 0 or 100.")
    index = np.searchsorted(t, grid, side="right") - 1
    out["Brake"] = frame.brake.to_numpy()[index] == 100
    out["nGear"] = frame.n_gear.to_numpy()[index]
    v = out.Speed.to_numpy() / 3.6
    out["Distance"] = np.r_[0, np.cumsum(np.diff(grid) * (v[:-1] + v[1:]) / 2)]
    return prepare_telemetry(out)


def telemetry_params(lap):
    start = pd.Timestamp(lap.DateStart)
    duration = lap.LapTime.total_seconds()
    return dict(session_key=int(lap.SessionKey), driver_number=int(lap.DriverNumber),
                **{"date>": (start - pd.Timedelta(1, unit="s")).isoformat(),
                   "date<": (start + pd.Timedelta(duration + 1, unit="s")).isoformat()})


def bundled_telemetry(lap):
    """Availability hint only; query() still verifies integrity when reading."""
    if lap.get("Source") != "OpenF1":
        return False
    key = hashlib.sha256(json.dumps(["car_data", telemetry_params(lap)], sort_keys=True).encode()).hexdigest()
    return (BUNDLED / f"{key}.json").is_file()


def open_lap_telemetry(lap):
    samples = query("car_data", **telemetry_params(lap))
    return convert_car_data(samples, lap.DateStart, lap.LapTime.total_seconds())
