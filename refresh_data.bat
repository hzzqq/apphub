@echo off
setlocal
cd /d "%~dp0"

echo [*] Fetching or refreshing real futures data, e.g. pulp SP ...
python backend/fetch_real_futures.py
if errorlevel 1 (
  echo [NOTE] Fetch failed: check internet, and install akshare via: python -m pip install akshare
) else (
  echo [ok] Done. Refresh futures-inventory in the browser to see real data.
)

REM 2) Bake real spread cache into futures-spread/index.html (so it works even with backend closed)
echo [*] Baking real spread cache into futures-spread/index.html ...
python backend/build_spread_cache.py
if errorlevel 1 (
  echo [NOTE] Spread cache build failed: check internet, and install akshare via: python -m pip install akshare
) else (
  echo [ok] Done. futures-spread now shows real snapshots even without the backend.
)
pause
