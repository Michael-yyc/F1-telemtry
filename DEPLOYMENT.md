# Publish the interactive dashboard

GitHub stores the source and reports. The Python/Streamlit application needs a
running Python host; GitHub Pages alone cannot run it.

## Streamlit Community Cloud

1. Open https://share.streamlit.io/ and sign in with your own GitHub account.
2. Authorise access to `Michael-yyc/F1-telemtry` if prompted.
3. Create an app from the repository with these settings:
   - Repository: `Michael-yyc/F1-telemtry`
   - Branch: `main`
   - Main file path: `app.py`
   - Advanced settings → Python version: **3.12**
4. Deploy and wait for the installation log to finish. No application secrets
   are needed for the default OpenF1 examples. The root `requirements.txt`
   installs the locked dependencies and the local analysis package.
5. Open the assigned app URL. Select **OpenF1 / 2023 / Bahrain / Q**, press
   **Load session**, and check **Q3 / SOFT / VER / PER**. Expect recorded
   **+0.138 s**, estimated **+0.087 s** and **−0.051 s** discrepancy.
6. Check Monza and Abu Dhabi too. Abu Dhabi deliberately shows the timing
   discrepancy warning; this is not a deployment failure.

The service assigns the URL; do not assume a particular `.streamlit.app` address
before deployment succeeds. After checking the hosted app, add its actual URL to
the GitHub repository's About/Website field and the README. Public visibility of
the app and repository is controlled in their respective account settings.

Bundled comparisons work without external downloads. New session or lap queries
need HTTPS access to `api.openf1.org`. Keep OpenF1 attribution and the noncommercial,
share-alike terms visible. Do not add F1 account credentials for the default source.

## Other Python hosts

Use Python 3.12, install `requirements.txt`, then run from the repository root:

```bash
python -m streamlit run app.py --server.address 0.0.0.0 --server.port "$PORT"
```

Set `PORT` to the port supplied by the host. Health endpoint: `/_stcore/health`.
Keep WebSocket support enabled. The default dataset is read-only and new queries
write only to `.cache/openf1/`; use a writable application directory for that cache.
The application is a noncommercial educational portfolio demonstration.
