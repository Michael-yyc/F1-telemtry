# Data access

The default source is now **OpenF1 historical data**, https://openf1.org/.
The bundled 2023 Bahrain, Monza and Abu Dhabi comparisons need no account,
subscription, API key or network. Other selections query api.openf1.org using
rate limiting and caching. See datasets/openf1/README.md for CC BY-NC-SA 4.0
attribution, noncommercial and share-alike terms and the checksummed manifest.

The published cloud public-network settings were verified active on 31 October
2026. No further setting change is needed for the default workflow.

## Optional FastF1 source

FastF1 is retained as an explicit alternative, not a fallback behind OpenF1.
Its upstream historical telemetry returned HTTP 401; its public mirror returned
HTTP 403. FastF1 3.9.0 supports Formula 1 account login, whose implementation
requires an active F1 TV subscription token. This path remains unvalidated here
because no credentials are present. It does not block the OpenF1 workflow.

Do not share passwords, tokens or cookies in chat or Git. If you independently
choose to use FastF1 on your own computer with an eligible account, its supported
interactive login is `python -m fastf1 auth f1tv --authenticate`. Do not invoke
interactive login inside Streamlit. Proxy-held secret placeholders are not
necessarily raw local login credentials.
