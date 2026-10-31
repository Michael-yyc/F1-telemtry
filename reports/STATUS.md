# Validation status — 31 October 2026

The default workflow now uses public **OpenF1 historical telemetry**, with
attributed real snapshots bundled for offline reproduction. No F1 TV login,
API key or further network-settings change is needed for the three examples.

## Verified

- All **58 tests pass**, including real-snapshot comparisons with network access
  disabled, data conversion, deleted-lap matching, checksums, and dashboard tests.
- Real OpenF1 session processing succeeds for Bahrain, Monza and Abu Dhabi 2023 Q3.
- Self-comparison gives zero and swapped-reference comparison reverses the sign.
- The real Bahrain notebook executed all four code cells with no saved errors.
- Annotated PNGs, interactive standalone HTMLs, CSVs and timing summaries were
  generated for all three sessions. The reviewed Bahrain case study is saved.
- The dashboard was opened in Chromium, loaded Bahrain, and displayed the real
  +0.138 s recorded gap. A screenshot is saved as dashboard-openf1.png.
- Twenty-three public API responses are bundled with attribution, licence,
  retrieval metadata and checked SHA-256 hashes (datasets/openf1/).

| Session | Recorded gap | Estimated gap | Discrepancy | Coverage |
| --- | ---: | ---: | ---: | ---: |
| Bahrain | +0.138 s | +0.087 s | -0.051 s | 99.89% |
| Monza | +0.381 s | +0.453 s | +0.072 s | 99.89% |
| Abu Dhabi | +0.726 s | +0.602 s | -0.124 s | 99.84% |

## Limits

Successful execution is not proof that the timing estimate meets an accuracy
threshold: **Abu Dhabi exceeds the 0.100 s discrepancy warning threshold**.
Source sampling and speed-derived distance constrain local timing claims.
The Bahrain case study discusses those limits alongside three reviewed sections.
Other sessions/laps outside the snapshot need network access and may lack data.
FastF1's optional authenticated route remains unvalidated and is not required.

Data and derived reports: OpenF1 contributors, https://openf1.org/,
CC BY-NC-SA 4.0 (noncommercial, attribution, share-alike). The earlier synthetic
validation example is labelled separately and is not historical evidence.

GitHub publication and application hosting are separate operations; see
`../DEPLOYMENT.md` for the prepared hosting configuration and hosted checks.
No public website deployment, new environment snapshot or fresh-task restoration
is claimed by these local validation results. The published startup configuration could not be edited after publication;
current instructions are preserved in ENVIRONMENT_START.md and the README.

## Hosted download-error fix

Reproduced the Q1 metadata selection shown in the hosted screenshot. Slow laps
(VER 132.516 s / PER 118.327 s) are now excluded by the qualifying pace heuristic.
An independent API request confirmed a provider-wide historical-download restriction
during live F1 sessions. The adapter now explains that restriction, bounds retries
for transient failures, and the dashboard offers a retry button and explicit offline
examples. Regression tests cover Q1 failure and recovery to bundled Q3 without an
unhandled exception. This does not remove OpenF1's access restriction or establish
availability of new downloads while it applies. No additional telemetry was bundled.
