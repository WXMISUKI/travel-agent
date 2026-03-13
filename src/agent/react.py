"""
ReAct Agent - 自主推理与行动智能体
基于ReAct (Reasoning + Acting) 模式的智能体实现
"""
import json
import re
from typing import Dict, List, Any, Optional, Callable
from ..llm.client import get_llm
from ..utils.logger import logger


class ReActStep:
    """ReAct推理步骤"""
    
    def __init__(self):
        self.thought: str = ""           # 思考分析
        self.action: str = ""             # 要执行的工具
        self.action_input: Dict = {}     # 工具参数
        self.observation: str = ""       # 观察结果
        self.is_final: bool = False       # 是否是最终答案
        self.error: Optional[str] = None  # 错误信息
    
    def to_dict(self) -> Dict:
        return {
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "is_final": self.is_final,
            "error": self.error
        }


class ReActAgent:
    """
    ReAct自主推理智能体
    
    工作流程:
    1. 用户输入 → LLM推理(Thought) + 选择工具(Action)
    2. 执行工具 → 获取结果(Observation)
    3. 基于结果 → 继续推理或给出最终答案
    4. 重复直到任务完成
    """
    
    # 工具描述 - 供LLM选择
    TOOL_DESCRIPTIONS = """
## 可用工具

1. **get_weather(city: str)** - 查询城市天气预报
   - 参数: city - 城市名称
   - 示例: get_weather("杭州")

2. **get_train_tickets(date: str, from_station: str, to_station: str, train_type: str = "G")** - 查询火车票
   - 参数: 
     - date: 出发日期 (格式: YYYY-MM-DD)
     - from_station: 出发站（必须是火车站名称，如"杭州东站"）
     - to_station: 到达站（必须是火车站名称）
     - train_type: 车次类型 (G高铁/D动车/K普快/T特快)
   - 注意: 如果用户输入城市名而非火车站名，必须先查火车站

3. **search_attractions(city: str, keyword: str = "景点")** - 搜索城市景点美食
   - 参数: city - 城市名称, keyword - 搜索关键词

4. **web_search(query: str)** - 通用网页搜索
   - 参数: query - 搜索关键词
   - 用途: 当专业工具失败时的降级方案

5. **parse_date(date_text: str)** - 解析自然语言日期
   - 参数: date_text - 如"明天"、"后天"、"下周一"、"3月15日"
   - 返回: 标准日期格式YYYY-MM-DD

6. **get_station_by_city(city: str)** - 查询城市附近的火车站
   - 参数: city - 城市名称（如"沙县"、"嘉兴"）
   - 返回: 该城市附近的火车站列表
   - 重要: 用户输入城市名时，必须先用此工具转换为火车站名
"""
    
    # 系统提示词
    SYSTEM_PROMPT = """你是旅行规划助手，一个智能的AI助手，能够自主推理并调用工具完成任务。

## 核心原则
1. **自主推理**: 你需要分析用户需求，思考应该调用什么工具
2. **智能决策**: 根据工具返回结果，自主决定下一步行动
3. **降级策略**: 专业工具失败时，立即使用web_search降级
4. **直接回答**: 完成任务后，直接给出有用信息，不要重复推理过程

## 重要规则
- 如果用户输入的是城市名（如"沙县"）而非火车站名，必须先调用get_station_by_city转换为火车站
- 日期如果不确定（如"明天"），必须先调用parse_date解析
- 如果专业工具返回错误或失败，立即使用web_search降级搜索
- 不要假设或编造信息，必须通过工具获取真实数据

## 输出格式
请严格按照以下格式输出你的推理：

```
Thought: [分析用户需求，当前应该做什么]
Action: [选择的工具名称，如 get_weather、web_search 等]
Action Input: [工具参数，JSON格式]
```

如果任务完成，请输出：

```
Thought: [分析用户需求]
Final Answer: [直接给用户的回复，包含查询到的信息]
```

## 工具列表
{tool_descriptions}

开始推理！"""
    
    def __init__(self, tool_executor: Optional[Callable] = None, max_iterations: int = 10):
        """
        初始化ReAct Agent
        
        Args:
            tool_executor: 工具执行函数，接收(tool_name, params)返回结果
            max_iterations: 最大迭代次数，防止无限循环
        """
        self.llm = get_llm()
        self.tool_executor = tool_executor
        self.max_iterations = max_iterations
        self.steps: List[ReActStep] = []
        self.conversation_history: List[Dict] = []
    
    def run(self, user_query: str, context: Dict = None) -> Dict:
        """
        运行ReAct Agent
        
        Args:
            user_query: 用户查询
            context: 额外上下文信息
            
        Returns:
            {
                "success": bool,
                "answer": str,           # 最终回答
                "steps": List[Dict],      # 推理步骤
                "error": Optional[str]    # 错误信息
            }
        """
        self.steps = []
        self.conversation_history = []
        
        logger.info(f"ReAct Agent开始处理: {user_query[:50]}...")
        
        # 构建系统提示词
        system_prompt = self.SYSTEM_PROMPT.format(
            tool_descriptions=self.TOOL_DESCRIPTIONS
        )
        
        # 添加上下文
        if context:
            context_info = f"\n## 额外上下文\n{json.dumps(context, ensure_ascii=False)}\n"
            system_prompt += context_info
        
        # 迭代推理
        for iteration in range(self.max_iterations):
            step = self._推理一步(user_query, system_prompt)
            self.steps.append(step)
            
            # 记录对话历史
            self.conversation_history.append({
                "thought": step.thought,
                "action": step.action,
                "action_input": step.action_input,
                "observation": step.observation
            })
            
            # 检查是否完成
            if step.is_final:
                logger.info(f"ReAct Agent完成，共{iteration + 1}步")
                return {
                    "success": True,
                    "answer": step.observation,  # Final Answer在observation中
                    "steps": [s.to_dict() for s in self.steps],
                    "error": None
                }
            
            # 检查是否有错误
            if step.error:
                logger.warning(f"步骤{iteration + 1}出错: {step.error}")
                # 继续尝试，不直接退出
        
        # 达到最大迭代次数
        logger.warning(f"达到最大迭代次数{self.max_iterations}")
        return {
            "success": False,
            "answer": "抱歉，我需要更多步骤来完成您的请求。",
            "steps": [s.to_dict() for s in self.steps],
            "error": "达到最大迭代次数"
        }
    
    def _推理一步(self, user_query: str, system_prompt: str) -> ReActStep:
        """
        执行一步推理
        
        Returns:
            ReActStep对象
        """
        step = ReActStep()
        
        # 构建对话上下文
        history_context = ""
        if self.conversation_history:
            history_context = "\n## 对话历史\n"
            for h in self.conversation_history[-5:]:  # 最近5步
                history_context += f"- Thought: {h['thought']}\n"
                history_context += f"- Action: {h['action']}\n"
                history_context += f"- Action Input: {json.dumps(h['action_input'], ensure_ascii=False)}\n"
                history_context += f"- Observation: {h['observation'][:200]}...\n\n"
        
        # 构建完整提示词
        full_prompt = f"""{system_prompt}

{history_context}

## 当前任务
用户: {user_query}

请开始推理："""
        
        # 调用LLM
        try:
            response = self.llm.chat(system_prompt, 
                f"{history_context}\n\n用户: {user_query}\n\n请按格式推理：")
            
            # 解析响应
            step = self._parse_llm_response(response)
            
            # 如果有Action，执行工具
            if step.action and not step.is_final:
                step.observation = self._执行工具(step.action, step.action_input)
                
        except Exception as e:
            logger.error(f"推理步骤异常: {e}")
            step.error = str(e)
            step.thought = "发生错误"
            step.observation = f"抱歉，处理时发生错误: {str(e)}"
            step.is_final = True
        
        return step
    
    def _parse_llm_response(self, response: str) -> ReActStep:
        """解析LLM响应，提取Thought、Action、Final Answer等"""
        step = ReActStep()
        
        # 尝试提取Final Answer
        final_match = re.search(r'Final Answer:\s*(.+?)(?=\n\n|\Z)', response, re.DOTALL | re.IGNORECASE)
        if final_match:
            step.is_final = True
            step.thought = re.search(r'Thought:\s*(.+?)(?=\n|$)', response, re.DOTALL | re.IGNORECASE)
            step.thought = step.thought.group(1).strip() if step.thought else "任务完成"
            step.observation = final_match.group(1).strip()
            return step
        
        # 提取Thought
        thought_match = re.search(r'Thought:\s*(.+?)(?=\n|$)', response, re.DOTALL | re.IGNORECASE)
        if thought_match:
            step.thought = thought_match.group(1).strip()
        
        # 提取Action
        action_match = re.search(r'Action:\s*(\w+)\s*(?:\(|$)', response, re.IGNORECASE)
        if action_match:
            step.action = action_match.group(1).strip()
        
        # 提取Action Input
        input_match = re.search(r'Action Input:\s*(\{[\s\S]*?\})(?=\n\n|\Z)', response, re.IGNORECASE)
        if input_match:
            try:
                step.action_input = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                # 尝试修复常见问题
                try:
                    # 尝试用eval
                    step.action_input = eval(input_match.group(1))
                except:
                    step.action_input = {"query": input_match.group(1)}
        
        # 如果没有提取到任何有效指令，可能是直接回答
        if not step.action and not step.is_final:
            step.is_final = True
            step.observation = response
            step.thought = "直接回答用户"
        
        return step
    
    def _执行工具(self, tool_name: str, params: Dict) -> str:
        """执行工具并返回结果"""
        
        # 检查工具是否存在
        from ..agent.tools import AVAILABLE_TOOLS
        if tool_name not in AVAILABLE_TOOLS:
            logger.warning(f"未知工具: {tool_name}")
            return f"未知工具: {tool_name}，请使用有效工具或直接回答"
        
        # 使用提供的执行器或默认执行器
        if self.tool_executor:
            try:
                result = self.tool_executor(tool_name, params)
                return self._简化工具结果(result, tool_name)
            except Exception as e:
                logger.error(f"工具执行失败: {e}")
                return f"工具执行失败: {str(e)}"
        else:
            # 使用默认执行方式
            try:
                from ..agent.tools import execute_tool
                result = execute_tool(tool_name, params)
                return self._简化工具结果(result, tool_name)
            except Exception as e:
                logger.error(f"工具执行失败: {e}")
                return f"工具执行失败: {str(e)}"
    
    def _简化工具结果(self, result: str, tool_name: str) -> str:
        """简化工具返回结果，便于LLM理解"""
        try:
            # 尝试解析JSON
            if isinstance(result, str) and result.startswith('{'):
                data = json.loads(result)
                
                # 针对不同工具做简化
                if tool_name == "get_station_by_city":
                    if "stations" in data and data["stations"]:
                        stations = [s["name"] for s in data["stations"][:3]]
                        return f"火车站列表: {', '.join(stations)}"
                    return f"未找到火车站: {data.get('error', '未知错误')}"
                
                elif tool_name == "parse_date":
                    if "parsed" in data:
                        return f"解析结果: {data['parsed']} ({data.get('weekday', '')})"
                    return f"解析失败: {data.get('error', '未知错误')}"
                
                elif tool_name == "get_train_tickets":
                    if "error" not in data:
                        # 简化车次信息
                        trains = data.get("trains", [])[:3]
                        if trains:
                            return f"查到{len(trains)}趟车次"
                        return "未查到火车票信息"
                    return f"查询失败: {data.get('error', '未知错误')}"
                
                elif tool_name == "get_weather":
                    if "error" not in data:
                        temp = data.get("temperature", "未知")
                        desc = data.get("description", "")
                        return f"天气: {desc}, 温度: {temp}°C"
                    return f"查询失败: {data.get('error', '未知错误')}"
                
                # 默认返回简化JSON
                return json.dumps(data, ensure_ascii=False)[:300]
            
            return str(result)[:500]
            
        except:
            return str(result)[:500]
    
    def get_thought_process(self) -> str:
        """获取思考过程文本"""
        lines = []
        for i, step in enumerate(self.steps, 1):
            lines.append(f"步骤{i}:")
            lines.append(f"  思考: {step.thought}")
            if step.action:
                lines.append(f"  行动: {step.action}")
                lines.append(f"  参数: {json.dumps(step.action_input, ensure_ascii=False)}")
            if step.observation:
                obs = step.observation[:200] + "..." if len(step.observation) > 200 else step.observation
                lines.append(f"  观察: {obs}")
            if step.error:
                lines.append(f"  错误: {step.error}")
            lines.append("")
        
        return "\n".join(lines)


# 全局Agent
_react_agent = None


def get_react_agent(tool_executor: Callable = None) -> ReActAgent:
    """获取ReAct Agent单例"""
    global _react_agent
    if _react_agent is None:
        _react_agent = ReActAgent(tool_executor=tool_executor)
    return _react_agent
