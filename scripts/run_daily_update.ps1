$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot
$env:HTTP_PROXY = "http://127.0.0.1:4780"
$env:HTTPS_PROXY = "http://127.0.0.1:4780"
$env:http_proxy = "http://127.0.0.1:4780"
$env:https_proxy = "http://127.0.0.1:4780"
python -m gold_data update
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python .\scripts\fetch_xau_data.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python .\scripts\fetch_gld_options_iv_data.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python .\scripts\fetch_fx_data.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python .\scripts\fetch_stock_index_data.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python .\scripts\fetch_stock_volatility_data.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python .\scripts\fetch_us_debt_data.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
