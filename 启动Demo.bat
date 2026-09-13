@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set NO_PROXY=127.0.0.1,localhost,0.0.0.0
set no_proxy=127.0.0.1,localhost,0.0.0.0
title SoundInsight Local Demo

echo ============================================================
echo  SoundInsight local demo starting...
echo  (first model load takes about 20-40 seconds)
echo.
echo  1) Open browser: http://127.0.0.1:7860
echo  2) Three tabs: single review / batch analyze / edge cases
echo  3) For video recording: use the [batch] tab and upload
echo     sample_reviews_100.csv
echo.
echo  Stop: press Ctrl+C in this window, or just close it
echo ============================================================
echo.

python demo_sound_v2.py

echo.
echo ============================================================
echo  Demo exited.
echo  If a red error appeared above, copy the text to DSH.
echo ============================================================
pause
