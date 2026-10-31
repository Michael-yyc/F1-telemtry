import numpy as np
import pandas as pd
import pytest

from f1_analyser.analysis import (DataQualityError, braking_windows, compare_laps,
                                  corner_metrics, prepare_telemetry)


def lap(speed=180.0, count=101):
    distance = np.linspace(0, 1000, count)
    return pd.DataFrame({"Distance": distance, "Time": distance / (speed / 3.6),
                         "Speed": speed, "Throttle": 100.0, "Brake": False, "nGear": 7})


def test_constant_speed_gap_matches_analytic_solution():
    result = compare_laps(lap(180), lap(144, 81), 20, 25)
    assert result.estimated_gap == pytest.approx(5)
    assert result.discrepancy == pytest.approx(0)
    assert result.coverage == 1


def test_same_lap_and_swapping_reference():
    a, b = lap(), lap(160, 91)
    assert np.allclose(compare_laps(a, a, 20, 20).aligned.Delta, 0)
    ab = compare_laps(a, b, 20, 22.5)
    ba = compare_laps(b, a, 22.5, 20)
    assert np.allclose(ab.aligned.Delta, -ba.aligned.Delta)


def test_discrete_channels_use_previous_sample_hold():
    a = lap()
    a.loc[a.Distance >= 500, ["Brake", "nGear"]] = [True, 3]
    result = compare_laps(a, a, 20, 20, step=7)
    assert set(result.aligned.Brake_ref) == {0, 1}
    assert set(result.aligned.nGear_ref) == {3, 7}
    assert result.aligned.loc[result.aligned.Distance < 500, "Brake_ref"].eq(0).all()


def test_no_extrapolation_or_forced_finish_gap():
    a, b = lap(), lap()
    b.Distance += 10
    result = compare_laps(a, b, 20, 20.3)
    assert result.aligned.Distance.min() == 10
    assert result.aligned.Distance.max() == 1000
    assert result.estimated_gap == 0
    assert result.discrepancy == pytest.approx(-0.3)
    assert result.warnings


@pytest.mark.parametrize("defect", ["missing", "nan", "timestamp", "reverse", "gap", "brake", "gear", "throttle", "speed"])
def test_rejects_broken_telemetry(defect):
    data = lap()
    if defect == "missing":
        data = data.drop(columns="Speed")
    elif defect == "nan":
        data.loc[4, "Speed"] = np.nan
    elif defect == "timestamp":
        data.loc[4, "Time"] = data.loc[3, "Time"]
    elif defect == "reverse":
        data.loc[4, "Distance"] = 0
    elif defect == "gap":
        data.loc[4:, "Time"] += 2
    elif defect == "brake":
        data["Brake"] = 0.5
    elif defect == "gear":
        data["nGear"] = 4.5
    elif defect == "throttle":
        data["Throttle"] = 101
    elif defect == "speed":
        data["Speed"] = 0
    with pytest.raises(DataQualityError):
        prepare_telemetry(data)


def test_rejects_partial_lap_and_nonoverlap():
    with pytest.raises(DataQualityError, match="98%"):
        compare_laps(lap(), lap().iloc[:80], 20, 20)
    with pytest.raises(DataQualityError, match="recorded lap time"):
        compare_laps(lap(), lap(), 30, 30)


def test_timedelta_and_repeated_distance():
    data = lap()
    data["Time"] = pd.to_timedelta(data.Time, unit="s")
    data.loc[1, "Distance"] = 0
    prepared = prepare_telemetry(data)
    assert prepared.Distance.is_unique
    assert prepared.Time.iloc[-1] == 20


def test_corner_metrics_and_elapsed_weighting():
    data = lap()
    data.loc[20:30, "Brake"] = True
    data.loc[20:40, "Throttle"] = 0
    data.loc[30, "Speed"] = 100
    metrics = corner_metrics(data, 100, 600)
    assert metrics["braking_onset_m"] == 200
    assert metrics["minimum_speed_kmh"] == 100
    assert metrics["high_throttle_return_m"] == 410
    # 50 intervals at 0.2 s minus 21 low-throttle intervals.
    assert metrics["high_throttle_seconds"] == pytest.approx(5.8)
    assert braking_windows(data) == [(100.0, 600.0)]


def test_already_braking_at_window_entry_is_unknown():
    data = lap()
    data.loc[10:50, "Brake"] = True
    metrics = corner_metrics(data, 200, 400)
    assert metrics["braking_onset_m"] is None
    assert metrics["high_throttle_return_m"] is None


def test_high_throttle_duration_weights_irregular_intervals():
    data = lap()
    data["Time"] = np.linspace(0, np.sqrt(20), len(data)) ** 2
    data.loc[20:40, "Throttle"] = 0
    metrics = corner_metrics(data, 100, 600)
    expected = data.Time.iloc[60] - data.Time.iloc[10] - (data.Time.iloc[41] - data.Time.iloc[20])
    assert metrics["high_throttle_seconds"] == pytest.approx(expected)


@pytest.mark.parametrize("step", [0, -1, np.nan, 5000])
def test_invalid_grid(step):
    with pytest.raises(ValueError):
        compare_laps(lap(), lap(), 20, 20, step=step)
