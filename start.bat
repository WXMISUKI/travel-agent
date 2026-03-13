@echo off
REM 旅行规划助手启动脚本

echo ========================================
echo   旅行规划助手 - Travel Agent
echo ========================================
echo.

REM 检查conda环境
echo [1/3] 检查conda环境...
call conda info --envs | findstr "langgraph-env"
if %errorlevel% neq 0 (
    echo 错误：未找到 langgraph-env conda环境
    echo 请先创建环境：conda create -n langgraph-env python=3.11
    pause
    exit /b 1
)

REM 激活conda环境
echo [2/3] 激活conda环境...
call conda activate langgraph-env

REM 安装依赖
echo [3/3] 安装依赖...
pip install -r requirements.txt -q

echo.
echo 依赖安装完成！
echo.

REM 启动服务
echo 启动FastAPI服务...
echo 访问 http://localhost:8000 查看API文档
echo.
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
