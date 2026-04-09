@echo off
REM Screenshot Feedback Service
REM Polls GitHub for screenshot feedback issues and processes them automatically.
REM
REM Prerequisites:
REM   - Python 3.10+
REM   - gh CLI (authenticated)
REM   - Git (authenticated for push)
REM
REM Environment variables (optional):
REM   SCREENSHOT_REPO       - GitHub repo (default: jonburchel/docs-screenshot)
REM   SCREENSHOT_REPO_DIR   - Local repo path (default: auto-detect)
REM   POLL_INTERVAL         - Seconds between polls (default: 60)

cd /d "%~dp0"
echo.
echo  ============================================
echo   Screenshot Feedback Service
echo  ============================================
echo.
echo  Repo: %SCREENSHOT_REPO%
echo  Polling for issues labeled 'screenshot-feedback'...
echo  Press Ctrl+C to stop.
echo.

python lib\feedback_service.py
