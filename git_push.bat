@echo off
REM ─────────────────────────────────────────────────────────
REM  git_push.bat — Pushar uppdateringar till GitHub
REM  Kör efter varje gång data.json uppdateras
REM ─────────────────────────────────────────────────────────

cd /d "C:\Users\vikto\OneDrive\Skrivbord\blavitttest"

echo.
echo === PUSHAR UPPDATERINGAR ===

git add app.py process_data.py fbref_updater.py requirements.txt
git add data.json match_data_2025.json match_data_2024.json 2>nul
git add README.md 2>nul

git commit -m "Uppdaterad data %date% %time:~0,5%"
git push

echo.
echo [OK] Pushad! Streamlit Cloud uppdateras inom ~1 minut.
pause
