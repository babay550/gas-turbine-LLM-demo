@echo off
chcp 65001 >nul 2>&1
title 燃气轮机智能运维系统 - 一键启动

echo ============================================
echo   燃气轮机运行优化智能体 - 一键启动
echo ============================================
echo.

:: ---------- 切换到脚本所在目录 ----------
cd /d "%~dp0"

:: ---------- 1. 检查 Python ----------
echo [1/5] 检查 Python ...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请安装 Python 3.12+ 并加入 PATH
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo       %PY_VER%

:: ---------- 2. 检查 Node.js ----------
echo [2/5] 检查 Node.js ...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请安装 Node.js 18+ 并加入 PATH
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') set NODE_VER=%%v
echo       Node.js %NODE_VER%

:: ---------- 3. 后端：依赖 + .env ----------
echo [3/5] 检查后端环境 ...
if not exist backend\.env (
    if exist backend\.env.example (
        copy backend\.env.example backend\.env >nul
        echo       已从 .env.example 创建 .env
    ) else (
        echo       [警告] 未找到 .env.example，跳过环境变量配置
    )
) else (
    echo       .env 已存在
)

if not exist backend\venv (
    echo       首次运行，创建虚拟环境 ...
    python -m venv backend\venv
    if %errorlevel% neq 0 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
)

echo       安装/更新后端依赖 ...
call backend\venv\Scripts\activate.bat
pip install -r backend\requirements.txt -q
call deactivate

:: ---------- 4. 前端：依赖 ----------
echo [4/5] 检查前端环境 ...
if not exist frontend\node_modules (
    echo       首次运行，安装前端依赖（可能需要几分钟）...
    cd frontend
    call npm install
    cd ..
) else (
    echo       node_modules 已存在，跳过安装
)

:: ---------- 5. 启动服务 ----------
echo [5/5] 启动服务 ...
echo.

:: 启动后端（新窗口）
start "后端 - FastAPI (port 8000)" cmd /k "cd /d "%~dp0backend" && call venv\Scripts\activate.bat && uvicorn src.api.main:app --reload --port 8000"

:: 等待后端就绪
echo       等待后端启动 ...
timeout /t 3 /nobreak >nul

:: 启动前端（新窗口）
start "前端 - Vite Dev Server (port 5173)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

:: 等待前端就绪后打开浏览器
echo       等待前端启动 ...
timeout /t 5 /nobreak >nul

echo.
echo ============================================
echo   启动完成！
echo   后端: http://localhost:8000
echo   前端: http://localhost:5173
echo ============================================
echo.
echo       正在打开浏览器 ...
start http://localhost:5173

echo.
echo 按任意键退出此窗口（后端/前端窗口不受影响）
pause >nul
