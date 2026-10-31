# OpenF1 historical snapshots

Source and attribution: **OpenF1 contributors**, https://openf1.org/,
https://github.com/br-g/openf1.

Licence: **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International**,
https://creativecommons.org/licenses/by-nc-sa/4.0/. Full text: LICENSE.txt.
Retain attribution, identify modifications, use noncommercially and share adapted
material under the same licence. No endorsement by OpenF1 or Formula 1 is implied.

The JSON response data is unchanged. Wrappers add endpoint/query parameters,
retrieval timestamps and source attribution. `manifest.json` lists source URLs,
record counts and SHA-256 hashes. Derived plots, aligned CSVs and reports in
`reports/generated/` carry the same CC BY-NC-SA 4.0 terms; changes are described
in the project README (filtering, mapping, interpolation, speed integration).

Snapshots cover 2023 Bahrain, Monza and Abu Dhabi qualifying metadata and the
selected VER/PER lap telemetry. Some metadata includes the full qualifying field;
only the selected car-telemetry windows are bundled. Other dashboard selections
can request new public historical data and use the ignored `.cache/openf1/`.
Do not assume a cache miss is an offline failure: new queries require the network.

Reproduce from the repository root with `python scripts/analyse_sessions.py --all`,
then `python scripts/bundle_open_data.py`. Existing bundled queries are preferred
for reproducibility. To intentionally refresh, preserve the old snapshots first,
then move the bundle and cache out of their configured paths and rerun online.
Do not change checksums to bypass an integrity failure.
