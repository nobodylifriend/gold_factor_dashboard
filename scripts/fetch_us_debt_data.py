from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin
import html
import json
import re
import sys

from bs4 import BeautifulSoup
import pandas as pd
from pypdf import PdfReader
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gold_data.catalog import refresh_indicator_directory

OUTPUT_DIR = ROOT / "data" / "us_debt"
START_DATE = pd.Timestamp("2025-01-01")
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}
TREASURY_API_BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
TREASURY_HOME_BASE = "https://home.treasury.gov"
FINANCING_ARCHIVE_URL = (
    "https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding/"
    "quarterly-refunding-archives/financing-estimates-by-calendar-year"
)
PAGE_SIZE = 10000

EXPECT_BORROWING_RE = re.compile(
    r"(?:During|Over) the ([A-Za-z]+ ?[–-] ?[A-Za-z]+(?: \d{4})?) quarter, (?:Treasury|the Treasury) expects to (borrow|pay down|issue) "
    r"\$([\d,.]+) (billion|trillion)(?: in| of)?(?: [A-Za-z-]+){0,4} marketable debt, "
    r"assuming an end-of-[A-Za-z]+ cash balance of \$([\d,.]+) (billion|trillion)",
    re.IGNORECASE,
)
ACTUAL_BORROWING_RE = re.compile(
    r"During the ([A-Za-z]+ ?[–-] ?[A-Za-z]+(?: \d{4})?) quarter, Treasury (borrowed|issued|paid down|payed down) "
    r"\$([\d,.]+) (billion|trillion)(?: in| of)?(?: [A-Za-z-]+){0,4} marketable debt.*?"
    r"cash balance of \$([\d,.]+) (billion|trillion)",
    re.IGNORECASE,
)
PRIOR_ESTIMATE_PATTERNS = (
    re.compile(
        r"estimated(?: [A-Za-z-]+){0,5} marketable borrowing(?: to total)?(?: of marketable debt)? "
        r"\$([\d,.]+) (billion|trillion)(?: and assumed|, assuming| with)"
        r"(?: an)? (?:end-of-[A-Za-z]+|ending quarter) cash balance of \$([\d,.]+) (billion|trillion)",
        re.IGNORECASE,
    ),
    re.compile(
        r"expected(?: [A-Za-z-]+){0,5} marketable borrowing(?: to total)?(?: of marketable debt)? "
        r"\$([\d,.]+) (billion|trillion)(?: with| and assumed)"
        r"(?: an)? (?:end-of-[A-Za-z]+|ending quarter) cash balance of \$([\d,.]+) (billion|trillion)",
        re.IGNORECASE,
    ),
    re.compile(
        r"estimated \$([\d,.]+) (billion|trillion) in (?:[A-Za-z-]+ )*marketable borrowing(?:, assuming| with| and assumed)"
        r"(?: an)? (?:end-of-[A-Za-z]+|ending quarter) cash balance of \$([\d,.]+) (billion|trillion)",
        re.IGNORECASE,
    ),
    re.compile(
        r"expected \$([\d,.]+) (billion|trillion) in (?:[A-Za-z-]+ )*marketable borrowing(?:, assuming| with| and assumed)"
        r"(?: an)? (?:end-of-[A-Za-z]+|ending quarter) cash balance of \$([\d,.]+) (billion|trillion)",
        re.IGNORECASE,
    ),
    re.compile(
        r"estimated a \$([\d,.]+) (billion|trillion) pay down in (?:[A-Za-z-]+ )*marketable debt(?: and assumed|, assuming| with)"
        r"(?: an)? (?:end-of-[A-Za-z]+|ending quarter) cash balance of \$([\d,.]+) (billion|trillion)",
        re.IGNORECASE,
    ),
)
HUMAN_DATE_RE = re.compile(r"\b([A-Z][a-z]+ \d{1,2}, \d{4})\b")


@dataclass(frozen=True)
class ArtifactSummary:
    name: str
    file_name: str
    start_date: str
    end_date: str
    rows: int
    notes: str = ""


def fetch_paginated(path: str, params: dict[str, str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    page_number = 1

    while True:
        page_params = dict(params)
        page_params["page[size]"] = str(PAGE_SIZE)
        page_params["page[number]"] = str(page_number)
        response = requests.get(
            urljoin(TREASURY_API_BASE, path),
            params=page_params,
            headers=HTTP_HEADERS,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data") or []
        if not rows:
            break
        records.extend(rows)
        if len(rows) < PAGE_SIZE:
            break
        page_number += 1

    return records


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def summarize(frame: pd.DataFrame, indicator_name: str, file_name: str, notes: str) -> ArtifactSummary:
    return ArtifactSummary(
        name=indicator_name,
        file_name=file_name,
        start_date=str(frame["date"].iloc[0]),
        end_date=str(frame["date"].iloc[-1]),
        rows=len(frame),
        notes=notes,
    )


def normalize_simple_series(
    frame: pd.DataFrame,
    value_column: str,
    source: str,
    *,
    scale: float = 1.0,
) -> pd.DataFrame:
    output = frame.copy()
    output["date"] = pd.to_datetime(output["record_date"]).dt.strftime("%Y-%m-%d")
    output["value"] = pd.to_numeric(output[value_column], errors="coerce") / scale
    output["source"] = source
    output = output.loc[output["date"] >= str(START_DATE.date())]
    output = output.dropna(subset=["value"])
    output = output.drop_duplicates(subset=["date"], keep="last")
    output = output.sort_values("date").reset_index(drop=True)
    return output[["date", "value", "source"]]


def fetch_intragovernmental_holdings() -> pd.DataFrame:
    rows = fetch_paginated(
        "v2/accounting/od/debt_to_penny",
        {
            "fields": "record_date,intragov_hold_amt",
            "filter": f"record_date:gte:{START_DATE.date()}",
            "sort": "record_date",
        },
    )
    frame = pd.DataFrame(rows)
    return normalize_simple_series(
        frame,
        "intragov_hold_amt",
        "treasury_fiscal_data:v2/accounting/od/debt_to_penny",
        scale=1_000_000.0,
    )


def fetch_marketable_outstanding() -> pd.DataFrame:
    rows = fetch_paginated(
        "v1/debt/mspd/mspd_table_1",
        {
            "fields": "record_date,total_mil_amt",
            "filter": f"record_date:gte:{START_DATE.date()},security_type_desc:eq:Total Marketable",
            "sort": "record_date",
        },
    )
    frame = pd.DataFrame(rows)
    return normalize_simple_series(
        frame,
        "total_mil_amt",
        "treasury_fiscal_data:v1/debt/mspd/mspd_table_1",
    )


def fetch_average_interest_rate() -> pd.DataFrame:
    rows = fetch_paginated(
        "v2/accounting/od/avg_interest_rates",
        {
            "fields": "record_date,avg_interest_rate_amt",
            "filter": (
                f"record_date:gte:{START_DATE.date()},security_type_desc:eq:Interest-bearing Debt,"
                "security_desc:eq:Total Interest-bearing Debt"
            ),
            "sort": "record_date",
        },
    )
    frame = pd.DataFrame(rows)
    return normalize_simple_series(
        frame,
        "avg_interest_rate_amt",
        "treasury_fiscal_data:v2/accounting/od/avg_interest_rates",
    )


def normalize_release_text(text: str) -> str:
    normalized = html.unescape(text)
    normalized = normalized.replace("\u00a0", " ").replace("\u200b", " ")
    normalized = normalized.replace("–", "-").replace("—", "-")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def parse_unit_amount_to_billions(raw_value: str, unit: str) -> float:
    value = float(raw_value.replace(",", ""))
    if unit.casefold() == "trillion":
        return value * 1000.0
    return value


def apply_borrowing_direction(value_billions: float, action: str) -> float:
    return -value_billions if "pay" in action.casefold() else value_billions


def extract_release_date_from_html(document: str) -> pd.Timestamp:
    soup = BeautifulSoup(document, "html.parser")

    selectors = (
        ("property", "article:published_time"),
        ("property", "article:modified_time"),
        ("property", "og:updated_time"),
        ("name", "date"),
        ("name", "DC.date"),
    )
    for attr_name, attr_value in selectors:
        tag = soup.find("meta", attrs={attr_name: attr_value, "content": True})
        if tag:
            return pd.Timestamp(tag["content"]).normalize()

    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        return pd.Timestamp(time_tag["datetime"]).normalize()

    match = re.search(r'"datePublished":"([^"]+)"', document)
    if match:
        return pd.Timestamp(match.group(1)).normalize()

    raise RuntimeError("Unable to determine release date from Treasury page")


def extract_release_date_from_pdf_text(text: str) -> pd.Timestamp:
    match = HUMAN_DATE_RE.search(text)
    if not match:
        raise RuntimeError("Unable to determine release date from financing estimate PDF")
    return pd.Timestamp(match.group(1)).normalize()


def extract_release_text_from_pdf(url: str) -> tuple[pd.Timestamp, str]:
    response = requests.get(url, headers=HTTP_HEADERS, timeout=60)
    response.raise_for_status()
    reader = PdfReader(BytesIO(response.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return extract_release_date_from_pdf_text(text), normalize_release_text(text)


def extract_release_text_from_html(url: str) -> tuple[pd.Timestamp, str]:
    response = requests.get(url, headers=HTTP_HEADERS, timeout=60)
    response.raise_for_status()
    document = response.text
    release_date = extract_release_date_from_html(document)
    soup = BeautifulSoup(document, "html.parser")

    meta = soup.find("meta", attrs={"property": "og:description", "content": True})
    if meta:
        return release_date, normalize_release_text(meta["content"])

    article = soup.find("article")
    text = article.get_text(" ", strip=True) if article else soup.get_text(" ", strip=True)
    return release_date, normalize_release_text(text)


def parse_financing_estimate_release(year: int, quarter: str, url: str) -> dict[str, object]:
    if url.lower().endswith(".pdf"):
        release_date, text = extract_release_text_from_pdf(url)
    else:
        release_date, text = extract_release_text_from_html(url)

    expected_matches = EXPECT_BORROWING_RE.findall(text)
    actual_match = ACTUAL_BORROWING_RE.search(text)
    if len(expected_matches) < 2 or actual_match is None:
        raise RuntimeError(f"Unable to parse financing estimate body: {url}")

    current_label, current_action, current_amount, current_unit, current_cash, current_cash_unit = expected_matches[0]
    next_label, next_action, next_amount, next_unit, next_cash, next_cash_unit = expected_matches[1]
    prior_label, prior_action, prior_amount, prior_unit, prior_cash, prior_cash_unit = actual_match.groups()

    current_amount_bil = apply_borrowing_direction(
        parse_unit_amount_to_billions(current_amount, current_unit),
        current_action,
    )
    next_amount_bil = apply_borrowing_direction(
        parse_unit_amount_to_billions(next_amount, next_unit),
        next_action,
    )
    prior_amount_bil = apply_borrowing_direction(
        parse_unit_amount_to_billions(prior_amount, prior_unit),
        prior_action,
    )

    trailing_text = text[actual_match.end() :]
    prior_estimate_amount = ""
    prior_estimate_unit = ""
    prior_estimate_action = ""
    prior_estimate_cash = ""
    prior_estimate_cash_unit = ""
    for pattern in PRIOR_ESTIMATE_PATTERNS:
        match = pattern.search(trailing_text)
        if match:
            prior_estimate_amount, prior_estimate_unit, prior_estimate_cash, prior_estimate_cash_unit = match.groups()
            prior_estimate_action = "pay down" if "pay down" in match.group(0).casefold() else "borrow"
            break

    return {
        "date": release_date.strftime("%Y-%m-%d"),
        "value": current_amount_bil,
        "release_year": year,
        "release_quarter": quarter,
        "current_quarter_label": current_label,
        "current_quarter_borrowing_bil": current_amount_bil,
        "current_quarter_end_cash_bil": parse_unit_amount_to_billions(current_cash, current_cash_unit),
        "next_quarter_label": next_label,
        "next_quarter_borrowing_bil": next_amount_bil,
        "next_quarter_end_cash_bil": parse_unit_amount_to_billions(next_cash, next_cash_unit),
        "prior_quarter_label": prior_label,
        "prior_quarter_actual_borrowing_bil": prior_amount_bil,
        "prior_quarter_end_cash_bil": parse_unit_amount_to_billions(prior_cash, prior_cash_unit),
        "prior_quarter_prior_estimate_bil": (
            apply_borrowing_direction(
                parse_unit_amount_to_billions(prior_estimate_amount, prior_estimate_unit),
                prior_estimate_action,
            )
            if prior_estimate_amount
            else pd.NA
        ),
        "prior_quarter_prior_estimate_end_cash_bil": (
            parse_unit_amount_to_billions(prior_estimate_cash, prior_estimate_cash_unit)
            if prior_estimate_cash
            else pd.NA
        ),
        "source_url": url,
        "source": "treasury_quarterly_refunding",
    }


def fetch_financing_estimate_releases() -> pd.DataFrame:
    response = requests.get(FINANCING_ARCHIVE_URL, headers=HTTP_HEADERS, timeout=60)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError("Unable to locate financing estimate archive table")

    releases: list[dict[str, object]] = []
    current_year = 0
    for row in table.find_all("tr"):
        year_header = row.find("th", attrs={"colspan": "4"})
        if year_header is not None:
            current_year = int(year_header.get_text(strip=True))
            continue
        if current_year < START_DATE.year:
            continue

        for cell in row.find_all("th"):
            link = cell.find("a", href=True)
            if link is None:
                continue
            quarter = re.sub(r"\s+", " ", cell.get_text(" ", strip=True).replace("\u200b", "")).strip()
            url = urljoin(TREASURY_HOME_BASE, link["href"])
            releases.append(parse_financing_estimate_release(current_year, quarter, url))

    frame = pd.DataFrame(releases)
    frame = frame.loc[frame["date"] >= str(START_DATE.date())]
    frame = frame.drop_duplicates(subset=["date"], keep="last")
    frame = frame.sort_values("date").reset_index(drop=True)
    return frame


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    intragov = fetch_intragovernmental_holdings()
    marketable = fetch_marketable_outstanding()
    avg_interest = fetch_average_interest_rate()
    borrowing = fetch_financing_estimate_releases()

    write_csv(OUTPUT_DIR / "Federal Debt Intragovernmental Holdings.csv", intragov)
    write_csv(OUTPUT_DIR / "Marketable Treasury Securities Outstanding.csv", marketable)
    write_csv(OUTPUT_DIR / "Average Interest Rate on Total Interest-Bearing Debt.csv", avg_interest)
    write_csv(OUTPUT_DIR / "Treasury Net Marketable Borrowing Estimate.csv", borrowing)

    artifacts = [
        summarize(
            intragov,
            "Federal Debt Intragovernmental Holdings",
            "Federal Debt Intragovernmental Holdings.csv",
            "Daily intragovernmental holdings from Treasury Debt to the Penny, converted to millions of dollars.",
        ).__dict__,
        summarize(
            marketable,
            "Marketable Treasury Securities Outstanding",
            "Marketable Treasury Securities Outstanding.csv",
            "Monthly total marketable Treasury securities outstanding from MSPD table 1, in millions of dollars.",
        ).__dict__,
        summarize(
            avg_interest,
            "Average Interest Rate on Total Interest-Bearing Debt",
            "Average Interest Rate on Total Interest-Bearing Debt.csv",
            "Monthly average interest rate on total interest-bearing debt from Treasury Fiscal Data.",
        ).__dict__,
        summarize(
            borrowing,
            "Treasury Net Marketable Borrowing Estimate",
            "Treasury Net Marketable Borrowing Estimate.csv",
            "Quarterly financing estimate releases from Treasury, with value equal to the current-quarter estimate in billions of dollars.",
        ).__dict__,
    ]

    manifest = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "base_start_date": str(START_DATE.date()),
        "artifacts": artifacts,
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    refresh_indicator_directory(ROOT)

    for artifact in artifacts:
        print(f"Wrote {OUTPUT_DIR / artifact['file_name']}")
    print(f"Wrote {OUTPUT_DIR / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
