"""FastF1 access and conservative lap selection."""
from pathlib import Path
import os

import fastf1
import pandas as pd

from .analysis import DataQualityError, prepare_telemetry


ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.environ.get("F1_CACHE_DIR", str(ROOT / ".cache" / "fastf1")))


def load_session(year: int, event: str | int, session_code: str = "Q", source="OpenF1"):
    if source == "OpenF1":
        from .open_data import load_open_session
        return load_open_session(year, event, session_code)
    if source != "FastF1":
        raise ValueError("Unknown telemetry source.")
    CACHE.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE))
    session = fastf1.get_session(year, event, session_code)
    # Race-control messages are required to establish which laps were deleted.
    session.load(telemetry=True, weather=True, messages=True)
    try:
        session.laps
    except fastf1.exceptions.DataNotLoadedError as exc:
        raise DataQualityError(
            "No lap telemetry was loaded. Check provider access and FastF1 account "
            "authentication; see reports/DATA_ACCESS.md. No replacement data was used."
        ) from exc
    return session


def eligible_laps(session) -> pd.DataFrame:
    """Timed, accurate, undeleted, dry, green-track laps without pit entry/exit."""
    laps = session.laps
    if getattr(session, "source", None) == "OpenF1":
        return laps.copy()
    valid = (laps.LapTime.notna() & laps.PitInTime.isna() & laps.PitOutTime.isna()
             & laps.IsAccurate.eq(True) & laps.Deleted.eq(False)
             & laps.TrackStatus.eq("1") & laps.Compound.isin(["SOFT", "MEDIUM", "HARD"]))
    result = laps.loc[valid].copy()
    result["Segment"] = "Session"
    if session.name in ("Qualifying", "Sprint Qualifying", "Sprint Shootout"):
        for label, segment in zip(("Q1", "Q2", "Q3"), laps.split_qualifying_sessions()):
            if segment is not None:
                result.loc[result.index.intersection(segment.index), "Segment"] = label
        result = result[result.Segment != "Session"]
    return result


def lap_telemetry(lap) -> pd.DataFrame:
    if lap.get("Source") == "OpenF1":
        from .open_data import open_lap_telemetry
        return open_lap_telemetry(lap)
    frame = lap.get_car_data(interpolate_edges=True).add_distance()
    return prepare_telemetry(frame)


def fastest_pair(session, driver_a: str, driver_b: str, segment: str = "Q3"):
    laps = eligible_laps(session)
    if session.name in ("Qualifying", "Sprint Qualifying", "Sprint Shootout"):
        laps = laps[laps.Segment == segment]
    a, b = laps[laps.Driver == driver_a], laps[laps.Driver == driver_b]
    if a.empty or b.empty:
        raise DataQualityError("No eligible laps for both drivers in this segment.")
    # Fastest common compound, ranked by the sum of each driver's fastest time.
    choices = []
    for compound in sorted(set(a.Compound) & set(b.Compound)):
        aa = a[a.Compound == compound].sort_values("LapTime").iloc[0]
        bb = b[b.Compound == compound].sort_values("LapTime").iloc[0]
        choices.append((aa.LapTime + bb.LapTime, aa, bb))
    if not choices:
        raise DataQualityError("Drivers have no eligible laps on a common tyre compound.")
    _, aa, bb = min(choices, key=lambda x: x[0])
    return aa, bb


def lap_summary(lap) -> dict:
    def seconds(key):
        value = lap.get(key)
        return None if pd.isna(value) else float(value.total_seconds())
    return {
        "driver": str(lap.Driver), "lap_number": int(lap.LapNumber),
        "lap_seconds": seconds("LapTime"),
        "lap_start_session_seconds": seconds("LapStartTime"),
        "sector_1_seconds": seconds("Sector1Time"),
        "sector_2_seconds": seconds("Sector2Time"),
        "sector_3_seconds": seconds("Sector3Time"),
        "compound": str(lap.Compound), "tyre_life": float(lap.TyreLife),
        "fresh_tyre": None if pd.isna(lap.FreshTyre) else bool(lap.FreshTyre),
    }
