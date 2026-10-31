"""Generate real case studies, plots and validation results. Never substitute data."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from f1_analyser.analysis import braking_windows, compare_laps, corner_metrics
from f1_analyser.data import fastest_pair, lap_summary, lap_telemetry, load_session
from f1_analyser.plots import telemetry_figure


CASES = [(2023, "Bahrain", "VER", "PER"), (2023, "Monza", "VER", "PER"),
         (2023, "Abu Dhabi", "VER", "PER")]


def analyse(year, event, driver_a, driver_b, output):
    session = load_session(year, event, "Q")
    a, b = fastest_pair(session, driver_a, driver_b)
    ta, tb = lap_telemetry(a), lap_telemetry(b)
    result = compare_laps(ta, tb, a.LapTime.total_seconds(), b.LapTime.total_seconds())
    identity = compare_laps(ta, ta, a.LapTime.total_seconds(), a.LapTime.total_seconds())
    reverse = compare_laps(tb, ta, b.LapTime.total_seconds(), a.LapTime.total_seconds())
    assert abs(identity.estimated_gap) < 1e-9, "Self-comparison failed"
    assert abs(reverse.estimated_gap + result.estimated_gap) < 1e-9, "Sign reversal failed"
    windows = braking_windows(ta)
    details = []
    for start, end in windows:
        details.append({"start_m": start, "end_m": end,
                        driver_a: corner_metrics(ta, start, end),
                        driver_b: corner_metrics(tb, start, end)})
    directory = output / f"{year}-{event.lower().replace(' ', '-')}"
    directory.mkdir(parents=True, exist_ok=True)
    result.aligned.to_csv(directory / "aligned.csv", index=False)
    # Bundle Plotly locally so exported reports do not need a CDN.
    interactive = telemetry_figure(result, driver_a, driver_b, windows)
    interactive.add_annotation(x=0, y=-.09, xref="paper", yref="paper", showarrow=False,
                               text="Data: OpenF1 contributors · https://openf1.org/ · CC BY-NC-SA 4.0 · derived noncommercial analysis")
    interactive.update_layout(margin=dict(b=95))
    interactive.write_html(directory / "telemetry.html", include_plotlyjs=True)
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True, layout="constrained")
    aligned = result.aligned
    for axis, channel, unit in zip(axes[:2], ("Speed", "Throttle"), ("km/h", "%")):
        axis.plot(aligned.Distance, aligned[f"{channel}_ref"], label=driver_a, color="#087e8b")
        axis.plot(aligned.Distance, aligned[f"{channel}_cmp"], label=driver_b, color="#cf5600")
        axis.set_ylabel(f"{channel} ({unit})")
        axis.legend(loc="upper right")
    axes[2].plot(aligned.Distance, aligned.Delta, color="#7141b8")
    axes[2].axhline(0, color="grey", lw=.7)
    axes[2].set(ylabel=f"{driver_b} − {driver_a} gap (s)", xlabel="Speed-integrated distance (m)")
    for number, section in enumerate(details, 1):
        for axis in axes:
            axis.axvspan(section["start_m"], section["end_m"], color="#7141b8", alpha=.08)
        aa, bb = section[driver_a], section[driver_b]
        axes[0].annotate(f"Section {number}\nmin {aa['minimum_speed_kmh']:.0f}/{bb['minimum_speed_kmh']:.0f} km/h",
                         xy=(aa["minimum_speed_m"], aa["minimum_speed_kmh"]),
                         xytext=(section["start_m"], 160 + 35 * (number % 2)), fontsize=8,
                         arrowprops=dict(arrowstyle="->"))
    for axis in axes:
        axis.grid(alpha=.2)
    fig.suptitle(f"OpenF1 · {year} {event} Q3 · {driver_a}/{driver_b}\nRecorded gap {result.recorded_gap:+.3f} s · estimate {result.estimated_gap:+.3f} s · discrepancy {result.discrepancy:+.3f} s")
    fig.supxlabel("Data: OpenF1 contributors · openf1.org · CC BY-NC-SA 4.0 · derived noncommercial analysis", fontsize=8)
    fig.savefig(directory / "comparison.png", dpi=150)
    plt.close(fig)
    summary = {"year": year, "event": event, "status": "passed", "segment": "Q3",
               "source": "OpenF1", "attribution": "OpenF1 contributors, https://openf1.org/", "licence": "CC BY-NC-SA 4.0",
               "laps": [lap_summary(a), lap_summary(b)],
               "recorded_gap_s": result.recorded_gap, "estimated_gap_s": result.estimated_gap,
               "discrepancy_s": result.discrepancy, "distance_coverage": result.coverage,
               "warnings": result.warnings, "sections": details,
               "self_comparison_gap_s": identity.estimated_gap,
               "swapped_gap_s": reverse.estimated_gap}
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    findings = []
    for number, section in enumerate(details, 1):
        aa, bb = section[driver_a], section[driver_b]
        def position(value):
            return "unknown" if value is None else f"{value:.0f} m"
        findings.append(
            f"### Section {number}: {section['start_m']:.0f}–{section['end_m']:.0f} m\n\n"
            f"{driver_a}/{driver_b} braking onsets: {position(aa['braking_onset_m'])} / {position(bb['braking_onset_m'])}. "
            f"Minimum sampled speeds: {aa['minimum_speed_kmh']:.1f} / {bb['minimum_speed_kmh']:.1f} km/h. "
            f"Return to ≥95% throttle after the minimum: {position(aa['high_throttle_return_m'])} / {position(bb['high_throttle_return_m'])}. "
            f"Observed high-throttle time: {aa['high_throttle_seconds']:.2f} / {bb['high_throttle_seconds']:.2f} s.\n\n"
            "These sampled observations do not establish the cause. Inspect the shaded section in telemetry.html before interpreting it as a corner.\n")
    title = (f"# {year} {session.event['EventName']} · Q3 · {driver_a} vs {driver_b}\n\n"
             f"Selected laps: {driver_a} lap {int(a.LapNumber)} and {driver_b} lap {int(b.LapNumber)}, {a.Compound}. "
             "Fastest eligible laps on a common compound in Q3. Phase is identified from OpenF1 race control; incomplete sectors, pit-out, recorded pit stops, matched deleted laps and caution records are excluded. Source completeness is not guaranteed.\n\n"
             f"Recorded gap ({driver_b} − {driver_a}): {result.recorded_gap:+.3f} s. "
             f"Estimated gap: {result.estimated_gap:+.3f} s; discrepancy: {result.discrepancy:+.3f} s; "
             f"distance coverage: {result.coverage:.2%}.\n\n"
             "See summary.json for sector times, tyre age and validation. Tyre condition, weather, traffic, fuel and setup are not controlled. "
             "Brake is binary, not pressure. Sampling and integrated-distance errors limit precision.\n\n"
             "Data: OpenF1 contributors (https://openf1.org/), CC BY-NC-SA 4.0. These noncommercial derived reports are shared under the same licence.\n\n")
    (directory / "case-study.md").write_text(title + "\n".join(findings))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports/generated"))
    parser.add_argument("--all", action="store_true", help="Validate all three planned sessions")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for case in CASES if args.all else CASES[:1]:
        try:
            result = analyse(*case, args.output)
        except Exception as exc:
            result = dict(year=case[0], event=case[1], status="failed", error=f"{type(exc).__name__}: {exc}")
        results.append(result)
        print(json.dumps(result, indent=2))
    (args.output / "validation.json").write_text(json.dumps(results, indent=2) + "\n")
    raise SystemExit(1 if any(result["status"] != "passed" for result in results) else 0)


if __name__ == "__main__":
    main()
