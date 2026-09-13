@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
title SoundInsight Final Pack

echo ============================================================
echo  Checking the 4 submission files and updating the final zip
echo ============================================================
echo.

python pack_final.py

echo.
echo  If all four show [OK], upload the zip to Tianchi.
pause
