# Deploy to Streamlit Community Cloud

This app is published as **`dashboard.py`** with demo data in **`publish_data/`** (copied into `outputs/` on first load).

## One-time setup

1. Push this repo to GitHub (already at `https://github.com/jdaiken/gliner_fraud_project`).
2. Sign in at [share.streamlit.io](https://share.streamlit.io) with GitHub.

## Create the app

| Setting | Value |
|--------|--------|
| Repository | `jdaiken/gliner_fraud_project` |
| Branch | `main` |
| Main file path | `dashboard.py` |
| Python version | **3.11** (recommended) |

Click **Deploy**. The first build installs `requirements.txt` (no PyTorch/GLiNER) and should finish in a few minutes.

## After deploy

- Open the app URL (e.g. `https://your-app-name.streamlit.app`).
- Demo data loads automatically from `publish_data/`.
- **Exports → Regenerate workpaper** works (openpyxl). Full pipeline re-run (GLiNER) is for local use only: `pip install -r requirements-local.txt` then `python run_pipeline.py`.

## Refresh bundled demo data (optional)

After running the pipeline locally:

```powershell
cd Gliner_fraud_project
python scripts/sync_publish_data.py
git add publish_data
git commit -m "Update Streamlit demo data bundle"
git push
```

Then reboot the app in Streamlit Cloud (**Manage app → Reboot**).

## Troubleshooting

| Issue | Fix |
|--------|-----|
| Blank / “No data loaded” | Confirm `publish_data/outputs/scored_transactions.csv` is in the repo on GitHub. |
| Build fails on memory | Use Python 3.11; do not add `torch` to `requirements.txt` for Cloud. |
| Slow first load | Normal; `@st.cache_data` warms up after the first tab view. |
