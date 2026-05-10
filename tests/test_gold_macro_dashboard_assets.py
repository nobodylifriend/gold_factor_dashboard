from pathlib import Path


def test_dashboard_html_contains_required_sections():
    html = Path("visuals/gold_macro_dashboard/index.html").read_text(encoding="utf-8")

    assert "黄金 / 美元 / 利率 信号矩阵" in html
    assert 'id="hero-entry-type"' in html
    assert 'id="start-date-display"' in html
    assert 'id="end-date-display"' in html
    assert 'id="apply-filters"' in html
    assert 'id="export-image"' in html
    assert 'id="quadrant-panel"' in html
    assert 'id="signal-checklist"' in html
    assert 'id="detail-charts"' in html
    assert 'id="chart-nasdaq100"' not in html


def test_dashboard_styles_define_fintech_theme_tokens():
    css = Path("visuals/gold_macro_dashboard/styles.css").read_text(encoding="utf-8")

    assert "--bg-base:" in css
    assert "--accent-gold:" in css
    assert ".hero-panel" in css
    assert ".chart-card" in css
    assert ".date-display" in css
    assert ".apply-button" in css
    assert ".signal-grid" in css
    assert ".quadrant-matrix" in css
