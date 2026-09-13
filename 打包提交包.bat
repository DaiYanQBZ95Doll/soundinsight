@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
title SoundInsight 最终打包

echo ============================================================
echo  正在检查四项提交物并更新 复赛作品.zip
echo ============================================================
echo.

python pack_final.py

echo.
echo 完成后请查看上方清单：四项都显示 [OK] 即可上传天池。
pause
