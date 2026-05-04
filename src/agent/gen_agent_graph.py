"""
旅行规划智能体 - 完整 Agent 架构可视化

本脚本创建一个完整的 LangGraph，展示：
- Agent 节点 (LLM 推理)
- 工具节点 (Tools)
- 数据源节点
- 降级策略

运行: python src/agent/gen_agent_graph.py
"""

import os
import sys

# 添加项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)


def create_full_agent_graph():
    """创建完整的 Agent LangGraph"""
    
    from typing import TypedDict
    from langgraph.graph import StateGraph, END
    
    # ========== 状态定义 ==========
    class AgentState(TypedDict):
        """Agent 状态"""
        messages: list  # 对话历史
        user_query: str  # 用户查询
        intent: str  # 意图
        entities: dict  # 实体
        plan_steps: list  # 执行计划步骤
        tool_results: dict  # 工具结果
        final_response: str  # 最终回复
        error: str  # 错误信息
    
    # ========== 节点函数 ==========
    
    def receive_message(state: AgentState) -> AgentState:
        """接收用户消息"""
        return {"messages": state.get("messages", []) + [state["user_query"]]}
    
    def agent_reasoning(state: AgentState) -> AgentState:
        """
        🤖 Agent 推理节点 - LLM 决策
        负责：意图识别、实体提取、决定调用哪些工具
        """
        query = state["user_query"]
        
        # 这里调用 LLM 进行推理
        # 实际实现中会调用豆包 LLM
        intent = "REASONING"  # 占位符
        
        return {
            "intent": intent,
            "entities": {"query": query}
        }
    
    def plan_tools(state: AgentState) -> AgentState:
        """
        📋 计划工具节点 - SmartPlanner
        负责：根据意图生成执行计划
        """
        intent = state.get("intent", "")
        
        # 根据意图生成步骤
        steps = []
        if "天气" in intent:
            steps = [{"tool": "get_weather", "params": {"city": "?"}}]
        elif "火车" in intent:
            steps = [
                {"tool": "get_station_by_city", "params": {"city": "?"}},
                {"tool": "get_train_tickets", "params": {"date": "?", "from": "?", "to": "?"}}
            ]
        elif "景点" in intent:
            steps = [{"tool": "search_attractions", "params": {"city": "?", "keyword": "景点"}}]
        else:
            steps = [{"tool": "web_search", "params": {"query": state["user_query"]}}]
        
        return {"plan_steps": steps}
    
    def execute_tools_node(state: AgentState) -> AgentState:
        """
        🔧 工具执行节点
        负责：调用各种工具获取数据
        """
        steps = state.get("plan_steps", [])
        results = {}
        
        for step in steps:
            tool = step.get("tool", "")
            # 实际执行工具
            results[tool] = {"status": "executed", "tool": tool}
        
        return {"tool_results": results}
    
    def generate_response_node(state: AgentState) -> AgentState:
        """
        💬 生成回复节点 - LLM
        负责：根据工具结果生成自然语言回复
        """
        return {"final_response": "处理完成"}
    
    def fallback_node(state: AgentState) -> AgentState:
        """
        🔄 降级搜索节点
        负责：工具失败时使用百度搜索兜底
        """
        return {"tool_results": {"web_search": {"status": "fallback"}}}
    
    # ========== 构建图 ==========
    
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("receive", receive_message)  # 接收消息
    workflow.add_node("reasoning", agent_reasoning)  # Agent 推理
    workflow.add_node("plan", plan_tools)  # 制定计划
    workflow.add_node("tools", execute_tools_node)  # 执行工具
    workflow.add_node("respond", generate_response_node)  # 生成回复
    workflow.add_node("fallback", fallback_node)  # 降级
    
    # 设置入口
    workflow.set_entry_point("receive")
    
    # 添加边
    workflow.add_edge("receive", "reasoning")
    workflow.add_edge("reasoning", "plan")
    workflow.add_edge("plan", "tools")
    workflow.add_edge("tools", "respond")
    workflow.add_edge("respond", END)
    workflow.add_edge("fallback", "respond")
    
    return workflow.compile()


def generate_mermaid_code(graph):
    """生成 Mermaid 代码"""
    
    # 完整的架构图
    mermaid = '''# 旅行规划智能体 - 完整 Agent 架构

```mermaid
flowchart TB
    subgraph INPUT["📥 输入层"]
        USER[用户请求<br/>User Query]
    end
    
    subgraph AGENT["🤖 Agent 核心层"]
        subgraph REASON["Agent 推理"]
            LLM1[Doubao LLM<br/>意图识别<br/>实体提取<br/>决策]
        end
        
        subgraph PLAN["📋 执行计划"]
            SP[SmartPlanner<br/>生成执行步骤<br/>TRIP_PLAN<br/>TRAIN_TICKETS<br/>WEATHER]
        end
    end
    
    subgraph TOOLS["🔧 Tools 工具层"]
        direction LR
        T1[get_weather<br/>天气查询]
        T2[get_train_tickets<br/>火车票查询]
        T3[search_attractions<br/>景点搜索]
        T4[get_station_by_city<br/>火车站查询]
        T5[parse_date<br/>日期解析]
        T6[web_search<br/>通用搜索]
    end
    
    subgraph DATA["📡 数据源层"]
        direction LR
        D1[apihz.cn<br/>天气/火车票]
        D2[Open-Meteo<br/>开源天气]
        D3[12306 MCP<br/>火车票]
        D4[百度搜索<br/>降级/景点]
    end
    
    subgraph OUTPUT["📤 输出层"]
        LLM2[Doubao LLM<br/>生成回复]
        RESP[返回用户]
    end
    
    USER --> LLM1
    LLM1 --> SP
    SP --> T1
    SP --> T2
    SP --> T3
    SP --> T4
    SP --> T5
    SP --> T6
    
    T1 --> D1
    T1 --> D2
    T1 --> D4
    T2 --> D3
    T2 --> D4
    T3 --> D4
    
    T1 -.->|失败| D4
    T2 -.->|失败| D4
    T3 -.->|失败| D4
    
    T1 --> LLM2
    T2 --> LLM2
    T3 --> LLM2
    T4 --> LLM2
    T5 --> LLM2
    T6 --> LLM2
    D4 --> LLM2
    
    LLM2 --> RESP
```

## 完整 LangGraph 执行流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant R as receive_message
    participant A as Agent推理
    participant P as SmartPlanner
    participant T as Tools层
    participant D as 数据源
    participant L as LLM回复
    participant O as 输出
    
    U->>R: 1. 用户请求
    R->>A: 2. 传递消息
    A->>P: 3. 意图+实体
    P->>T: 4. 执行计划步骤
    T->>D: 5. 调用数据源
    D-->>T: 6. 返回数据
    T-->>P: 7. 返回结果
    P->>L: 8. 收集结果
    L->>O: 9. 生成回复
    O-->>U: 10. 流式返回
```

## Agent 节点详解

| 节点 | 功能 | 说明 |
|------|------|------|
| receive | 接收消息 | 记录用户输入 |
| reasoning | Agent推理 | LLM分析意图和实体 |
| plan | 制定计划 | SmartPlanner生成步骤 |
| tools | 执行工具 | 调用各个工具 |
| respond | 生成回复 | LLM整合结果 |
| fallback | 降级搜索 | 失败时兜底 |
'''
    
    return mermaid


def main():
    """主函数"""
    print("=" * 70)
    print("旅行规划智能体 - 完整 Agent 架构可视化")
    print("=" * 70)
    
    # 创建完整 Agent 图
    print("\n📊 创建 LangGraph Agent 图...")
    agent_graph = create_full_agent_graph()
    
    # 生成 Mermaid 代码
    print("\n📝 生成 Mermaid 代码...")
    mermaid_code = generate_mermaid_code(agent_graph)
    print(mermaid_code)
    
    # 尝试生成 PNG
    print("\n🖼️ 生成 PNG 图片...")
    try:
        png_data = agent_graph.get_graph().draw_mermaid_png()
        output_path = os.path.join(project_root, "langgraph_full_agent.png")
        with open(output_path, "wb") as f:
            f.write(png_data)
        print(f"✅ 图片已保存: {output_path}")
    except Exception as e:
        print(f"⚠️ PNG 生成失败: {e}")
    
    print("\n" + "=" * 70)
    print("提示: 将 Mermaid 代码复制到 https://mermaid.live/ 查看")
    print("=" * 70)


if __name__ == "__main__":
    main()
