#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . ".env"
  set +a
fi

python -m gold_data update
python scripts/fetch_xau_data.py
python scripts/fetch_gld_options_iv_data.py
python scripts/fetch_fx_data.py
python scripts/fetch_stock_index_data.py
python scripts/fetch_stock_volatility_data.py
python scripts/fetch_us_debt_data.py
python scripts/build_gold_macro_dashboard_data.py
