# GitHub Pages Dashboard Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GitHub Pages and GitHub Actions deployment path that publishes the existing static dashboard and refreshes its data daily without modifying existing application files.

**Architecture:** Keep the current dashboard as a static site under `visuals/gold_macro_dashboard`. Add one workflow to publish that directory to GitHub Pages and another workflow to run the existing Python update pipeline on a schedule, commit refreshed data back to the repository, and let the Pages workflow redeploy from the updated branch state.

**Tech Stack:** GitHub Actions, GitHub Pages, YAML workflows, Bash helper script, Python dependency manifest, Markdown deployment guide, pytest

---

### Task 1: Lock deployment artifacts with tests

**Files:**
- Create: `tests/test_github_pages_setup.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_github_pages_files_exist():
    required = [
        Path(".github/workflows/deploy-pages.yml"),
        Path(".github/workflows/daily-update.yml"),
        Path("requirements.github-pages.txt"),
        Path("scripts/run_daily_update_github.sh"),
        Path("docs/deployment/github-pages.md"),
    ]
    missing = [str(path) for path in required if not path.exists()]
    assert not missing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_github_pages_setup.py -v`
Expected: FAIL because the deployment files do not exist yet.

- [ ] **Step 3: Expand the test to assert key workflow content**

```python
def test_deploy_workflow_targets_pages():
    text = Path(".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
    assert "actions/configure-pages" in text
    assert "actions/upload-pages-artifact" in text
    assert "actions/deploy-pages" in text


def test_daily_update_workflow_runs_pipeline_and_commits():
    text = Path(".github/workflows/daily-update.yml").read_text(encoding="utf-8")
    assert "schedule:" in text
    assert "workflow_dispatch:" in text
    assert "python -m gold_data update" in text
    assert "python scripts/build_gold_macro_dashboard_data.py" in text
    assert "git push" in text
```

- [ ] **Step 4: Run test to verify it still fails**

Run: `pytest tests/test_github_pages_setup.py -v`
Expected: FAIL because the workflow files still do not exist.

### Task 2: Add GitHub deployment artifacts

**Files:**
- Create: `.github/workflows/deploy-pages.yml`
- Create: `.github/workflows/daily-update.yml`
- Create: `requirements.github-pages.txt`
- Create: `scripts/run_daily_update_github.sh`

- [ ] **Step 1: Implement the Pages deploy workflow**

Create a workflow that:
- runs on `push` to `main`
- uses `actions/configure-pages`
- uploads `visuals/gold_macro_dashboard`
- deploys with `actions/deploy-pages`

- [ ] **Step 2: Implement the daily update workflow**

Create a workflow that:
- runs on `schedule` and `workflow_dispatch`
- installs Python dependencies from `requirements.github-pages.txt`
- writes `.env` from `secrets.FRED_API_KEY`
- runs `bash scripts/run_daily_update_github.sh`
- commits changed `data/` and `visuals/gold_macro_dashboard/data/`

- [ ] **Step 3: Add the GitHub-specific dependency manifest**

List the Python packages needed by the current update pipeline.

- [ ] **Step 4: Add the GitHub helper script**

Wrap the current update commands in a Bash script so the workflow stays short and the update sequence is explicit.

- [ ] **Step 5: Run the targeted test**

Run: `pytest tests/test_github_pages_setup.py -v`
Expected: PASS

### Task 3: Document the install path

**Files:**
- Create: `docs/deployment/github-pages.md`

- [ ] **Step 1: Write the failing documentation assertion**

Add test coverage that checks the deployment guide mentions:
- creating a public GitHub repo
- setting the `FRED_API_KEY` secret
- enabling GitHub Pages with GitHub Actions
- pushing to `main`

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_github_pages_setup.py -v`
Expected: FAIL until the guide exists with the required content.

- [ ] **Step 3: Write the deployment guide**

Document:
- which files were added
- how to create the GitHub repo
- how to push the code
- how to add the secret
- how to enable Pages
- how to trigger the first update manually
- how to inspect workflow logs

- [ ] **Step 4: Run the targeted test**

Run: `pytest tests/test_github_pages_setup.py -v`
Expected: PASS

### Task 4: Final verification

**Files:**
- Test: `tests/test_github_pages_setup.py`

- [ ] **Step 1: Run deployment artifact test**

Run: `pytest tests/test_github_pages_setup.py -v`
Expected: PASS

- [ ] **Step 2: Summarize manual GitHub-side steps**

Report the exact repository settings and secrets the user must configure after uploading the repo.
