$Root = Split-Path -Parent $PSScriptRoot
$env:MEALPREPPER_DATA_DIR = Join-Path $Root "data"
$env:MEALPREPPER_WWW_DIR = Join-Path $Root "mealprepper\www"
$env:MEALPREPPER_API_PORT = "5051"

Set-Location $Root
python -m pip install -r requirements.txt
python (Join-Path $Root "mealprepper\main.py")
