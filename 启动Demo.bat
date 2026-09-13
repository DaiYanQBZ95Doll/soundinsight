@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
REM 本机若有系统代理，需让 localhost 绕过代理，否则 gradio 启动自检会 502
set NO_PROXY=127.0.0.1,localhost,0.0.0.0
set no_proxy=127.0.0.1,localhost,0.0.0.0
title SoundInsight 本地 Demo

echo ============================================================
echo  SoundInsight 本地 Demo 启动中（首次加载模型约 20-40 秒）
echo.
echo  启动成功后：
echo    1) 浏览器打开 http://127.0.0.1:7860
echo    2) 三个页签：单条评论 / 批量分析 / 边界案例
echo    3) 录屏演示用「批量分析」页上传 sample_reviews_100.csv
echo.
echo  停止 Demo：在本窗口按 Ctrl+C，或直接关掉本窗口
echo ============================================================
echo.

python demo_sound_v2.py

echo.
echo ============================================================
echo  Demo 已退出。
echo  若上方出现红色报错，请把报错文字复制给 DSH。
echo ============================================================
pause
