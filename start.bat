@echo off
setlocal

rem ============================================================
rem  学生成绩管理系统 - 一键启动脚本
rem  用法：双击本文件，自动准备环境并启动前后端服务
rem ============================================================

rem 切换到脚本所在目录（项目根目录）
cd /d "%~dp0"

echo ================================================
echo    学生成绩管理系统 - 一键启动
echo ================================================
echo.

rem ----- 1. 检查并准备后端环境 -----
if not exist "backend\.venv\Scripts\python.exe" (
    echo [1/5] 首次运行，正在创建后端虚拟环境...
    where python >nul 2>nul
    if errorlevel 1 (
        echo [错误] 未检测到 Python，请先安装 Python 3.9 以上版本
        echo.
        pause
        exit /b 1
    )
    python -m venv backend\.venv
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败
        echo.
        pause
        exit /b 1
    )
    echo [2/5] 正在安装后端依赖（首次约需 1-2 分钟）...
    backend\.venv\Scripts\python.exe -m pip install --upgrade pip -q
    backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -q
    if errorlevel 1 (
        echo [错误] 后端依赖安装失败，请检查网络后重试
        echo.
        pause
        exit /b 1
    )
    echo.
) else (
    echo [1/5] 后端环境已就绪
)

rem ----- 2. 定位 Node.js / npm -----
rem 优先用系统 PATH 里的 npm；找不到则用 WorkBuddy 管理的 node
set "NODE_BIN="
where npm >nul 2>nul
if not errorlevel 1 goto npm_ready
for /d %%d in ("%USERPROFILE%\.workbuddy\binaries\node\versions\*") do (
    if exist "%%d\npm.cmd" set "NODE_BIN=%%d"
)
if defined NODE_BIN (
    set "PATH=%NODE_BIN%;%PATH%"
    goto npm_ready
)
echo [错误] 未检测到 Node.js / npm
echo        请到 https://nodejs.org/ 下载安装 LTS 版本后重试
echo.
pause
exit /b 1

:npm_ready
echo [2/5] Node.js 环境已就绪

rem ----- 3. 检查并准备前端环境 -----
if not exist "frontend\node_modules" (
    echo [3/5] 首次运行，正在安装前端依赖...
    pushd frontend
    call npm install
    popd
    if errorlevel 1 (
        echo [错误] 前端依赖安装失败，请检查网络后重试
        echo.
        pause
        exit /b 1
    )
    echo.
) else (
    echo [3/5] 前端环境已就绪
)

rem ----- 4. 启动后端 -----
echo [4/5] 正在启动后端服务（端口 8080）...
cd /d "%~dp0backend"
start "Student-Score-Backend" cmd /k ".venv\Scripts\python.exe main.py"
cd /d "%~dp0"

rem ----- 5. 启动前端 -----
echo [5/5] 正在启动前端服务（端口 5173）...
cd /d "%~dp0frontend"
start "Student-Score-Frontend" cmd /k "npm run dev"
cd /d "%~dp0"

echo.
echo ================================================
echo    启动完成！
echo.
echo    前端页面 : http://localhost:5173/
echo    API 文档 : http://localhost:8080/docs
echo.
echo    浏览器即将自动打开前端页面
echo    关闭对应的命令行窗口即可停止对应服务
echo ================================================
echo.

rem 等待服务就绪后自动打开浏览器
timeout /t 5 /nobreak >nul
start http://localhost:5173/

endlocal
