"""
LangGraph 工作流可视化工具

使用方法：
    python -m src.agent.workflow
    
这将自动生成 langgraph_workflow.png 图片。

或者运行此脚本查看 Mermaid 流程图代码：
    python src/utils/visualize.py
"""

# 直接运行 workflow.py 来生成图片
if __name__ == "__main__":
    import subprocess
    import sys
    import os
    
    print(__doc__)
    
    # 切换到项目根目录
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 运行 workflow.py
    result = subprocess.run(
        [sys.executable, "-m", "src.agent.workflow"],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)