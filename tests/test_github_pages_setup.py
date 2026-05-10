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


def test_deploy_workflow_targets_pages():
    text = Path(".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
    assert "actions/configure-pages" in text
    assert "actions/upload-pages-artifact" in text
    assert "actions/deploy-pages" in text
    assert "visuals/gold_macro_dashboard" in text


def test_daily_update_workflow_runs_pipeline_and_commits():
    text = Path(".github/workflows/daily-update.yml").read_text(encoding="utf-8")
    assert "schedule:" in text
    assert "workflow_dispatch:" in text
    assert "bash scripts/run_daily_update_github.sh" in text
    assert "git push" in text

    script = Path("scripts/run_daily_update_github.sh").read_text(encoding="utf-8")
    assert "python -m gold_data update" in script
    assert "python scripts/build_gold_macro_dashboard_data.py" in script


def test_requirements_include_update_dependencies():
    text = Path("requirements.github-pages.txt").read_text(encoding="utf-8")
    for package in ("pandas", "requests", "PyYAML", "beautifulsoup4", "pypdf"):
        assert package in text


def test_deployment_guide_covers_manual_setup():
    text = Path("docs/deployment/github-pages.md").read_text(encoding="utf-8")
    assert "public repository" in text
    assert "FRED_API_KEY" in text
    assert "GitHub Pages" in text
    assert "GitHub Actions" in text
    assert "main" in text
