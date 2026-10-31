"""Pure calculations: no network, UI, or FastF1 objects required."""
from dataclasses import dataclass

import numpy as np
import pandas as pd


CHANNELS = ("Distance", "Time", "Speed", "Throttle", "Brake", "nGear")


class DataQualityError(ValueError):
    """Telemetry cannot support a meaningful lap comparison."""


@dataclass
class Comparison:
    aligned: pd.DataFrame
    recorded_gap: float
    estimated_gap: float
    discrepancy: float
    coverage: float
    warnings: list[str]


def prepare_telemetry(frame: pd.DataFrame, max_sample_gap: float = 1.5) -> pd.DataFrame:
    """Require ordered, complete channels; reject gaps before interpolation.

    Time is seconds from the lap start (or a pandas timedelta). Brake and gear
    remain discrete. Repeated distances are collapsed to their latest sample.
    """
    missing = set(CHANNELS) - set(frame.columns)
    if missing:
        raise DataQualityError(f"Missing channels: {', '.join(sorted(missing))}")
    data = frame.loc[:, CHANNELS].copy().reset_index(drop=True)
    if pd.api.types.is_timedelta64_dtype(data.Time):
        data["Time"] = data.Time.dt.total_seconds()
    try:
        data = data.astype(float)
    except (ValueError, TypeError) as exc:
        raise DataQualityError("Telemetry channels must contain numeric values.") from exc
    if len(data) < 20 or not np.isfinite(data.to_numpy()).all():
        raise DataQualityError("Need at least 20 complete, finite telemetry samples.")
    dt = np.diff(data.Time)
    if np.any(dt <= 0):
        raise DataQualityError("Telemetry timestamps must increase strictly.")
    if np.max(dt) > max_sample_gap:
        raise DataQualityError(f"Missing telemetry: sample gap exceeds {max_sample_gap:g} s.")
    if np.any(np.diff(data.Distance) < 0):
        raise DataQualityError("Distance must not run backwards.")
    if (data.Speed <= 0).any() or (data.Speed > 400).any():
        raise DataQualityError("Speed outside the supported timed-lap range (0–400 km/h).")
    if not data.Throttle.between(0, 100).all():
        raise DataQualityError("Throttle must be between 0 and 100 percent.")
    if not data.Brake.isin([0, 1]).all() or not data.nGear.isin(range(9)).all():
        raise DataQualityError("Brake must be binary and gear an integer from 0 to 8.")
    data = data.drop_duplicates("Distance", keep="last").reset_index(drop=True)
    if len(data) < 20 or data.Distance.iloc[-1] - data.Distance.iloc[0] < 100:
        raise DataQualityError("Insufficient distance coverage for a timed lap.")
    return data


def _on_grid(data: pd.DataFrame, grid: np.ndarray) -> dict:
    out = {}
    for channel in ("Speed", "Throttle", "Time"):
        out[channel] = np.interp(grid, data.Distance, data[channel])
    # Previous sample hold: no fractional gears or invented braking transitions.
    idx = np.searchsorted(data.Distance, grid, side="right") - 1
    for channel in ("Brake", "nGear"):
        out[channel] = data[channel].to_numpy()[idx]
    return out


def compare_laps(reference: pd.DataFrame, comparison: pd.DataFrame,
                 reference_seconds: float, comparison_seconds: float,
                 step: float = 5.0) -> Comparison:
    """Align by absolute distance and integrate reciprocal speed on overlap.

    delta = elapsed comparison - elapsed reference; positive means comparison
    is behind. No stretching to force the official finish gap and no extrapolation.
    Speed integration is approximate; recorded lap times remain authoritative.
    """
    if not np.isfinite([reference_seconds, comparison_seconds, step]).all() or min(reference_seconds, comparison_seconds, step) <= 0:
        raise ValueError("Lap durations and grid spacing must be positive and finite.")
    a, b = prepare_telemetry(reference), prepare_telemetry(comparison)
    start = max(a.Distance.iloc[0], b.Distance.iloc[0])
    end = min(a.Distance.iloc[-1], b.Distance.iloc[-1])
    full_span = max(a.Distance.iloc[-1], b.Distance.iloc[-1]) - min(a.Distance.iloc[0], b.Distance.iloc[0])
    coverage = (end - start) / full_span
    if end <= start or coverage < 0.98:
        raise DataQualityError("Laps share less than 98% distance coverage.")
    for data, duration in ((a, reference_seconds), (b, comparison_seconds)):
        if (data.Time.iloc[-1] - data.Time.iloc[0]) / duration < 0.98:
            raise DataQualityError("Telemetry spans less than 98% of the recorded lap time.")
    grid = np.unique(np.r_[np.arange(start, end, step), end])
    if len(grid) < 3:
        raise ValueError("Grid spacing is too large for this lap.")
    aa, bb = _on_grid(a, grid), _on_grid(b, grid)
    aligned = pd.DataFrame({"Distance": grid})
    for label, values in (("ref", aa), ("cmp", bb)):
        for channel, value in values.items():
            aligned[f"{channel}_{label}"] = value
        reciprocal_speed = 3.6 / values["Speed"]  # s/m, speed input is km/h
        increments = np.diff(grid) * (reciprocal_speed[:-1] + reciprocal_speed[1:]) / 2
        aligned[f"Elapsed_{label}"] = np.r_[0.0, np.cumsum(increments)]
    aligned["Delta"] = aligned.Elapsed_cmp - aligned.Elapsed_ref
    recorded = comparison_seconds - reference_seconds
    estimated = float(aligned.Delta.iloc[-1])
    warnings = []
    if coverage < 0.995:
        warnings.append("Distance overlap is below 99.5%; the trace omits part of a lap.")
    if abs(estimated - recorded) > 0.1:
        warnings.append("Estimated finish gap differs from timing by over 0.100 s; treat local gains cautiously.")
    return Comparison(aligned, recorded, estimated, estimated - recorded, float(coverage), warnings)


def corner_metrics(frame: pd.DataFrame, start: float, end: float,
                   high_throttle: float = 95.0) -> dict:
    """Metrics from original samples, not interpolated grid points.

    Braking onset is a false→true transition inside the window. If braking was
    already active at entry, onset is unknown. Throttle return is the first
    below→high transition after the minimum speed, unless already high there.
    High-throttle duration uses previous-sample hold over elapsed-time intervals.
    """
    if not np.isfinite([start, end, high_throttle]).all() or end <= start or not 0 <= high_throttle <= 100:
        raise ValueError("Supply an ordered corner window and throttle threshold from 0 to 100.")
    data = prepare_telemetry(frame)
    window = data.loc[data.Distance.between(start, end)]
    if len(window) < 3:
        raise DataQualityError("Corner window needs at least three original samples.")
    minimum = window.Speed.idxmin()
    onset = data.Brake.eq(1) & data.Brake.shift(1).eq(0)
    braking = window.loc[onset.loc[window.index]]
    returns = data.Throttle.ge(high_throttle) & data.Throttle.shift(1).lt(high_throttle)
    exits = window.loc[(window.index > minimum) & returns.loc[window.index]]
    dt = np.diff(window.Time)
    return {
        "braking_onset_m": None if braking.empty else float(braking.Distance.iloc[0]),
        "minimum_speed_kmh": float(window.Speed.min()),
        "minimum_speed_m": float(data.loc[minimum, "Distance"]),
        "high_throttle_return_m": None if exits.empty else float(exits.Distance.iloc[0]),
        "high_throttle_seconds": float(np.sum(dt * window.Throttle.iloc[:-1].ge(high_throttle).to_numpy())),
        "observed_start_m": float(window.Distance.iloc[0]),
        "observed_end_m": float(window.Distance.iloc[-1]),
    }


def braking_windows(frame: pd.DataFrame, limit: int = 3) -> list[tuple[float, float]]:
    """Propose separated braking sections for manual inspection, not corner IDs."""
    data = prepare_telemetry(frame)
    onsets = data.loc[data.Brake.eq(1) & data.Brake.shift(1).eq(0), "Distance"]
    windows = []
    for distance in onsets:
        start, end = max(float(data.Distance.iloc[0]), distance - 100), min(float(data.Distance.iloc[-1]), distance + 400)
        if not windows or start > windows[-1][1]:
            windows.append((float(start), float(end)))
        if len(windows) == limit:
            break
    return windows
