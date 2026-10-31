# Review a real comparison

Run `python scripts/analyse_sessions.py --all` after enabling data-provider access.
Use the generated files as measurements to investigate, not a finished causal explanation.

For Bahrain, document VER/PER lap numbers, Q3 membership, SOFT compound, tyre age,
fresh-tyre status, lap start times and available weather. Explain what remains
uncontrolled. If conditions differ substantially, select a different pair in the
dashboard and explain the tradeoff.

For each of three manually checked corner sections:

1. Identify the corner(s) and record the distance window. Verify the proposed
   section contains the braking zone, minimum and exit you intended to compare.
2. Inspect the original samples around brake onset and throttle return; quote the
   local time/distance sampling interval rather than implying exact positions.
3. State the measured speed, onset and high-throttle differences. Read the gap
   change across the same section and check whether it supports the observation.
4. Annotate a plot or capture the dashboard with the section visible. Distinguish
   an observation from a possible explanation. Note confounders and missing data.

Report the recorded gap, estimated finish gap, discrepancy and distance coverage.
Inspect whether accumulated distance drift changes the apparent alignment. Check
self-comparison and swapped-lap results in summary.json. Repeat with a slightly
different window and grid spacing to test sensitivity before making strong claims.

Finish with screenshots or a short screen recording, reproducible commands and
three concise findings. Only then turn actual achievements into CV bullets.
