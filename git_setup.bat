@echo off
REM ─────────────────────────────────────────────────────────
REM  git_setup.bat — Initierar Git och pushar till GitHub
REM  Kör EN GÅNG när du sätter upp repot
REM ─────────────────────────────────────────────────────────

cd /d "C:\Users\vikto\OneDrive\Skrivbord\blavitttest"

echo.
echo === ALLSVENSKAN ANALYTICS — GIT SETUP ===
echo.

REM Initiera git om det inte redan finns
if not exist ".git" (
    git init
    echo [OK] Git initierat
) else (
    echo [OK] Git finns redan
)

REM Lägg till remote — BYT UT URL mot ditt GitHub-repo!
echo.
echo Ange ditt GitHub repo-URL (tex https://github.com/vikto/allsvenskan-analytics.git):
set /p REPO_URL="> "

git remote remove origin 2>nul
git remote add origin %REPO_URL%
echo [OK] Remote satt till %REPO_URL%

REM Första commit
git add app.py process_data.py fbref_updater.py requirements.txt
git add README.md .gitignore
git add data.json match_data_2025.json match_data_2024.json
git add -f .streamlit/config.toml

git commit -m "Initial commit: Allsvenskan Analytics"
git branch -M main
git push -u origin main

echo.
echo ============================================
echo  Klart! Repot är nu uppe på GitHub.
echo  Gå till share.streamlit.io for att deploya.
echo ============================================
pause
