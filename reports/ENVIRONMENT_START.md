# Current startup guidance

Use the existing `/workspace/F1-telemtry` checkout, not a new worktree.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

Select OpenF1 / 2023 / Bahrain / Q, then Q3 / SOFT / VER / PER. The three bundled
historical comparisons need no credentials or network. Regenerate them with
`.venv/bin/python scripts/analyse_sessions.py --all`. New selections may download
from api.openf1.org; the published public-network settings are already active.

Check local health/root responses; do not assume a server process survives
restoration. The executed real-data notebook, reviewed case study and screenshot
are saved in the checkout. See README.md and reports/STATUS.md for current evidence.

The environment's published startup configuration could not be edited after
publication. This repository file supersedes its outdated blocked-data guidance;
no new startup draft or snapshot publication is claimed. Keep snapshots and code
changes in this checkout when making the next environment version.
