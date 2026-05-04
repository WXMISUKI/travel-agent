git push origin master && git push github master
🚀 启动指南
步骤1：激活conda环境并安装依赖
bash
conda activate myenv

# 安装依赖
pip install -r d:\AI\AIcode\travel-agent\requirements.txt
步骤2：启动12306 MCP服务
参考 d:\AI\AIcode\travel-agent\mcps\12306-mcp 目录下的文档启动MCP服务。

步骤3：启动后端
bash
conda activate myenv
cd d:\AI\AIcode\travel-agent
uvicorn src.main:app --reload --port 8000
步骤4：启动前端
用浏览器直接打开 d:\AI\AIcode\travel-agent\frontend\index.html，或者：

bash
cd d:\AI\AIcode\travel-agent\frontend
python -m http.server 5173
然后访问 http://localhost:5173