@echo off
REM install.bat — SoundInsight 一键安装（Windows）
REM 步骤：检测 Python -> 创建虚拟环境 -> 安装依赖 -> 下载模型权重 -> 自检
chcp 65001 >nul
setlocal

echo ============================================
echo  SoundInsight 一键安装
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+ 并勾选 "Add to PATH"
    pause
    exit /b 1
)

if not exist .venv (
    echo [1/4] 创建虚拟环境 .venv ...
    python -m venv .venv
) else (
    echo [1/4] 虚拟环境已存在，跳过
)

call .venv\Scripts\activate.bat

echo [2/4] 安装依赖（requirements.txt）...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络后重试
    pause
    exit /b 1
)

echo [3/4] 下载模型权重（ModelScope 镜像）...
python download_models.py
if errorlevel 1 (
    echo [错误] 模型下载失败，请重试 download_models.py
    pause
    exit /b 1
)

echo [4/4] 自检（加载模型并推理一条样例）...
python -c "from predict_core import predict_single; r = predict_single('The bass is missing and there is constant static.'); print('自检结果:', '音质负面' if r['pred'] else '正常', 'prob=', r['prob'])" 
if errorlevel 1 (
    echo [错误] 自检失败，请查看上方报错
    pause
    exit /b 1
)

echo.
echo 安装完成！
echo   - 启动 Demo 界面：.venv\Scripts\python demo_sound_v2.py
echo   - 启动 HTTP API：.venv\Scripts\python api_server.py
echo   - 生成洞察报告：.venv\Scripts\python soundinsight_agent.py --csv 你的评论.csv
pause
