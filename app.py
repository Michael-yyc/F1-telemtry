"""Run with: streamlit run app.py"""
import pandas as pd
import streamlit as st

from f1_analyser.analysis import DataQualityError, braking_windows, compare_laps, corner_metrics
from f1_analyser.data import eligible_laps, lap_summary, lap_telemetry, load_session
from f1_analyser.plots import telemetry_figure


st.set_page_config(page_title="F1 · Lap Lab", page_icon="🏎️", layout="wide")
st.title("F1 · Lap Lab")
st.caption("Explore where time is gained. Compare the measurements, then question the explanation.")


@st.cache_resource(show_spinner="Loading timing and telemetry…")
def cached_session(year, event, code, source):
    return load_session(year, event, code, source)


with st.sidebar:
    st.header("Session")
    with st.form("session"):
        source = st.selectbox("Data source", ["OpenF1", "FastF1"])
        year = st.number_input("Season", min_value=2023 if source == "OpenF1" else 2018, max_value=2026, value=2023)
        event = st.text_input("Country, circuit or session key (OpenF1); event or round (FastF1)", "Bahrain")
        code = st.selectbox("Session", ["Q", "R", "SQ", "S", "FP1", "FP2", "FP3"])
        submitted = st.form_submit_button("Load session", type="primary")
    st.caption("Downloads are cached locally. First load may take a few minutes.")
    st.caption("OpenF1 historical data: no login. CC BY-NC-SA 4.0 · noncommercial use, attribution and share-alike. Source: openf1.org.")
    st.info("Positive gap: comparison driver is behind the reference. Recorded timing is authoritative.")

if submitted:
    st.session_state["selection"] = (int(year), event.strip(), code, source)
if "selection" not in st.session_state:
    st.info("Choose a session and press **Load session** to begin. Suggested case: 2023 Bahrain qualifying, VER vs PER in Q3.")
    st.stop()

try:
    selected_year, selected_event, selected_code, selected_source = st.session_state["selection"]
    event_key = int(selected_event) if selected_event.isdigit() else selected_event
    session = cached_session(selected_year, event_key, selected_code, selected_source)
    laps = eligible_laps(session)
    if laps.empty:
        raise DataQualityError("No eligible timed laps in this session.")
except Exception as exc:
    st.error(f"Session unavailable: {exc}")
    st.info("Check the season, event and session. Data may be missing or the data provider may be unreachable. No results have been substituted.")
    st.stop()

st.subheader(f"{selected_year} {session.event['EventName']} · {session.name}")
if selected_source == "OpenF1":
    st.caption("Source: OpenF1. Selected laps have complete consistent sectors, dry tyres, no pit-out or recorded pit stop, and no matched deletion or caution record. Qualifying phase comes from race control. Source records may be incomplete; this is not FastF1's accuracy flag.")
else:
    st.caption("FastF1: accurate timing, undeleted, dry compound, green track, no pit entry or exit. Telemetry is checked after selection.")
segment = st.selectbox("Qualifying segment / session", sorted(laps.Segment.unique()), index=len(laps.Segment.unique()) - 1)
laps = laps[laps.Segment == segment]
compound = st.selectbox("Common tyre compound", sorted(laps.Compound.unique()))
laps = laps[laps.Compound == compound]
drivers = sorted(laps.Driver.unique())
if len(drivers) < 2:
    st.warning("This selection has fewer than two drivers. Select another segment or compound.")
    st.stop()
left, right = st.columns(2)
with left:
    driver_a = st.selectbox("Reference driver", drivers, index=drivers.index("VER") if "VER" in drivers else 0)
with right:
    opponents = [driver for driver in drivers if driver != driver_a]
    driver_b = st.selectbox("Comparison driver", opponents, index=opponents.index("PER") if "PER" in opponents else 0)


def choose_lap(driver, column, label):
    choices = laps[laps.Driver == driver].sort_values("LapTime")
    with column:
        index = st.selectbox(label, list(choices.index), format_func=lambda i: f"Lap {int(choices.loc[i].LapNumber)} · {choices.loc[i].LapTime.total_seconds():.3f} s · tyre age {choices.loc[i].TyreLife:g}")
    return choices.loc[index]


a = choose_lap(driver_a, left, "Reference lap")
b = choose_lap(driver_b, right, "Comparison lap")
try:
    ta, tb = lap_telemetry(a), lap_telemetry(b)
    result = compare_laps(ta, tb, a.LapTime.total_seconds(), b.LapTime.total_seconds())
except (DataQualityError, ValueError, KeyError) as exc:
    st.error(f"These laps cannot be compared reliably: {exc}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Recorded gap", f"{result.recorded_gap:+.3f} s")
c2.metric("Estimated gap", f"{result.estimated_gap:+.3f} s")
c3.metric("Estimate − recorded", f"{result.discrepancy:+.3f} s")
c4.metric("Distance overlap", f"{result.coverage:.2%}")
st.dataframe(pd.DataFrame([lap_summary(a), lap_summary(b)]), hide_index=True, width="stretch")
if a.TyreLife != b.TyreLife or a.FreshTyre != b.FreshTyre:
    st.warning("Tyre age or fresh-tyre status differs. Same compound does not guarantee comparable tyre condition.")
st.caption("Fuel, setup, track evolution, traffic and weather can differ. Teammates reduce car differences but do not isolate driving technique.")
if selected_source == "OpenF1":
    st.caption("Distance is derived by integrating speed. Lap-edge samples are interpolated only when bracketed. Throttle is clipped to 0–100%; brake maps OpenF1's 0/100 states to off/on. Fresh-tyre status is unavailable.")
for warning in result.warnings:
    st.warning(warning)

with st.expander("Corner sections and metric definitions", expanded=False):
    st.write("Defaults are proposed braking sections, not identified circuit corners. Adjust the windows after inspecting the plots. Metrics use original samples; uncertainty is at least the local sampling interval.")
    threshold = st.slider("High-throttle threshold (%)", 80, 100, 95)
    defaults = braking_windows(ta)
    if not defaults:
        st.warning("No braking onsets detected; inspect the telemetry manually.")
    windows = []
    for i, window in enumerate(defaults):
        windows.append(st.slider(f"Section {i + 1} distance (m)", float(result.aligned.Distance.min()), float(result.aligned.Distance.max()),
                                 (max(float(result.aligned.Distance.min()), window[0]), min(float(result.aligned.Distance.max()), window[1])), step=5.0))
st.plotly_chart(telemetry_figure(result, driver_a, driver_b, windows), width="stretch")

st.subheader("Section findings")
for i, (start, end) in enumerate(windows, 1):
    st.markdown(f"**Section {i} · {start:.0f}–{end:.0f} m**")
    try:
        ma, mb = corner_metrics(ta, start, end, threshold), corner_metrics(tb, start, end, threshold)
        st.dataframe(pd.DataFrame([ma, mb], index=[driver_a, driver_b]), width="stretch")
        st.write(f"{driver_b}'s minimum sampled speed is {mb['minimum_speed_kmh'] - ma['minimum_speed_kmh']:+.1f} km/h relative to {driver_a}. High-throttle duration in the observed section is {mb['high_throttle_seconds'] - ma['high_throttle_seconds']:+.2f} s different.")
    except (DataQualityError, ValueError) as exc:
        st.warning(str(exc))
st.download_button("Download aligned telemetry (CSV)", result.aligned.to_csv(index=False), "lap-comparison.csv", "text/csv")
with st.expander("Method and limitations"):
    st.write("Speed and throttle are interpolated on a 5 m grid over the shared distance range. Brake and gear use previous-sample hold. The gap integrates 1/speed by the trapezoidal rule; it is approximate and is not forced to match recorded timing. Distances are integrated per lap and are not rescaled. Missing gaps over 1.5 s and lap coverage below 98% are rejected. Brake is on/off, not pressure. A missing onset or throttle return is unknown, not zero.")
