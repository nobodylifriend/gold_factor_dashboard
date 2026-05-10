# GitHub Pages Deployment

This repository can publish the existing dashboard as a public website with GitHub Pages and keep the data refreshed daily with GitHub Actions.

## Added Files

- `.github/workflows/deploy-pages.yml`
- `.github/workflows/daily-update.yml`
- `requirements.github-pages.txt`
- `scripts/run_daily_update_github.sh`

## What This Setup Does

- `deploy-pages.yml` publishes `visuals/gold_macro_dashboard` to GitHub Pages whenever `main` receives dashboard changes.
- `daily-update.yml` runs once per day and on manual trigger.
- The daily workflow installs Python dependencies, writes `.env` from the `FRED_API_KEY` secret, runs the existing update pipeline, commits refreshed `data/` files, and pushes the result back to `main`.
- The new push to `main` then triggers GitHub Pages deployment automatically.

## Required Repository Setup

1. Create a new **public repository** on GitHub.
2. Push this project to the `main` branch of that repository.
3. In GitHub, open `Settings` -> `Secrets and variables` -> `Actions`.
4. Create a repository secret named `FRED_API_KEY`.
5. Paste your real FRED API key as the secret value.
6. Open `Settings` -> `Actions` -> `General`.
7. Under `Workflow permissions`, select `Read and write permissions`.
8. Save the setting so the daily workflow can commit refreshed data back to `main`.
9. Open `Settings` -> `Pages`.
10. Under `Build and deployment`, set `Source` to `GitHub Actions`.

## First-Time Install Steps

### 1. Create the GitHub repository

Create a new public repository on GitHub. Do not initialize it with a README if you already have this local project ready to push.

### 2. Push your local project

Run these commands from the repository root after replacing the URL:

```powershell
git remote add origin https://github.com/<your-user>/<your-repo>.git
git branch -M main
git add .
git commit -m "chore: prepare GitHub Pages deployment"
git push -u origin main
```

If you already have a remote, skip `git remote add origin`.

### 3. Add the FRED secret

The daily workflow depends on `FRED_API_KEY`. Without it, the scheduled update job will fail before `python -m gold_data update`.

### 4. Enable GitHub Pages

After the first push:

1. Open the repository on GitHub.
2. Go to `Settings` -> `Pages`.
3. Set the build source to `GitHub Actions`.
4. Wait for the `Deploy GitHub Pages` workflow to finish.

The site URL will look like:

```text
https://<your-user>.github.io/<your-repo>/
```

## How to Trigger the First Data Refresh

1. Open the `Actions` tab in GitHub.
2. Select `Daily Data Update`.
3. Click `Run workflow`.
4. Choose the `main` branch.
5. Start the job.

If the job succeeds, it will:

- refresh `data/`
- rebuild `visuals/gold_macro_dashboard/data/dashboard_data.json`
- commit the updated files to `main`
- trigger the Pages deployment workflow again

## How to Check Status

### Data update workflow

Open `Actions` -> `Daily Data Update`.

Look for these steps:

- `Install dependencies`
- `Write .env for FRED access`
- `Run daily update pipeline`
- `Commit refreshed data`

### Pages deployment workflow

Open `Actions` -> `Deploy GitHub Pages`.

Look for these steps:

- `Configure GitHub Pages`
- `Upload Pages artifact`
- `Deploy to GitHub Pages`

## Notes

- The cron schedule is `22:15 UTC`, which is `06:15` in China Standard Time on the next day.
- The workflows do not change application code. They only publish the existing static dashboard and refresh generated data.
- If a third-party data source blocks GitHub-hosted runners, the daily workflow may fail even though GitHub Pages itself is configured correctly.
