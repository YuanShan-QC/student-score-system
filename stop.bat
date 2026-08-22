@echo off
setlocal

rem ============================================================
rem  学生成绩管理系统 - 停止服务脚本
rem  用法：双击本文件，停止后端（8080）和前端（5173）服务
rem ============================================================

echo ================================================
echo    学生成绩管理系统 - 停止服务
echo ================================================
echo.

rem ----- 停止后端（8080 端口）-----
echo [1/2] 正在停止后端服务（端口 8080）...
set "found="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do (
    set "found=1"
    taskkill /F /PID %%a >nul 2>nul
    echo        已停止进程 PID %%a
)
if not defined found echo        后端服务未在运行

echo.

rem ----- 停止前端（5173 端口）-----
echo [2/2] 正在停止前端服务（端口 5173）...
set "found="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do (
    set "found=1"
    taskkill /F /PID %%a >nul 2>nul
    echo        已停止进程 PID %%a
)
if not defined found echo        前端服务未在运行

echo.
echo ================================================
echo    完成！所有服务已停止。
echo ================================================
echo.
pause

endlocal
