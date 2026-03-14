"""
增强版工具适配器 - 智能工具调用链管理
核心功能：
1. 工具调用链自动修复
2. 参数自动补全和修正
3. 多级降级策略
4. 工具执行结果反思
"""
import json
import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from ..utils.logger import logger


class ToolStatus(Enum):
    """工具执行状态"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # 部分成功
    NEEDS_RETRY = "needs_retry"
    NEEDS_FALLBACK = "needs_fallback"


@dataclass
class ToolResult:
    """工具执行结果"""
    status: ToolStatus
    data: Any
    original_params: Dict[str, Any] = field(default_factory=dict)
    fixed_params: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int = 1
    fallback_used: bool = False
    reflection: Optional[str] = None  # 反思结果
    
    def is_success(self) -> bool:
        return self.status == ToolStatus.SUCCESS
    
    def needs_fallback(self) -> bool:
        return self.status in [ToolStatus.FAILED, ToolStatus.NEEDS_FALLBACK]


@dataclass 
class ToolChainConfig:
    """工具链配置"""
    max_retries: int = 2  # 最大重试次数
    enable_auto_fix: bool = True  # 自动修复参数
    enable_reflection: bool = True  # 反思机制
    enable_fallback: bool = True  # 降级策略


class ToolAdapter:
    """
    增强版工具适配器
    
    提供：
    - 参数自动修复
    - 智能重试
    - 多级降级
    - 结果反思
    """
    
    def __init__(self, config: Optional[ToolChainConfig] = None):
        self.config = config or ToolChainConfig()
        self._tool_registry: Dict[str, Dict[str, Any]] = {}
        
    def register_tool(self, name: str, func: Callable, 
                     description: str = "",
                     param_schema: Optional[Dict] = None,
                     fix_hints: Optional[Dict[str, Callable]] = None):
        """注册工具及其修复提示"""
        self._tool_registry[name] = {
            "func": func,
            "description": description,
            "param_schema": param_schema or {},
            "fix_hints": fix_hints or {}  # 参数修复函数
        }
        logger.info(f"工具注册: {name}")
    
    def execute(self, tool_name: str, params: Dict[str, Any],
                fallback: Optional[Callable] = None) -> ToolResult:
        """
        执行工具，带自动修复和降级
        """
        if tool_name not in self._tool_registry:
            return ToolResult(
                status=ToolStatus.FAILED,
                data=None,
                error=f"未知工具: {tool_name}"
            )
        
        tool_info = self._tool_registry[tool_name]
        func = tool_info["func"]
        
        # ===== 第一步：参数修复 =====
        if self.config.enable_auto_fix:
            fixed_params = self._fix_params(tool_name, params)
            if fixed_params != params:
                logger.info(f"参数已自动修复: {params} -> {fixed_params}")
                params = fixed_params
        
        # ===== 第二步：执行工具 =====
        result = self._execute_with_retry(func, params)
        
        # ===== 第三步：结果反思 =====
        if self.config.enable_reflection and result.needs_fallback():
            reflection = self._reflect_on_failure(tool_name, params, result)
            result.reflection = reflection
            
            # 如果反思认为可以重试
            if reflection.get("should_retry"):
                retry_params = reflection.get("fixed_params")
                if retry_params:
                    logger.info(f"根据反思结果重试: {retry_params}")
                    result = self._execute_with_retry(func, retry_params)
        
        # ===== 第四步：降级处理 =====
        if result.needs_fallback() and fallback:
            logger.info(f"执行降级策略: {tool_name}")
            fallback_result = self._execute_fallback(fallback, tool_name, params)
            if fallback_result:
                result = fallback_result
                result.fallback_used = True
        
        return result
    
    def _fix_params(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """修复工具参数"""
        fixed = params.copy()
        
        if tool_name == "get_train_tickets":
            # 修复火车站名称问题
            fixed = self._fix_train_ticket_params(fixed)
        elif tool_name == "get_weather":
            fixed = self._fix_weather_params(fixed)
        elif tool_name == "get_station_by_city":
            fixed = self._fix_station_params(fixed)
            
        return fixed
    
    def _fix_train_ticket_params(self, params: Dict) -> Dict:
        """修复火车票查询参数"""
        fixed = params.copy()
        
        # 检查站名是否包含无效字符
        for key in ["from_station", "to_station"]:
            if key in fixed:
                station = str(fixed[key])
                
                # 清理站名中的无关信息
                # 例如："南昌局集团公司将鹰厦线原龙江站更名为龙江村..." 
                # 应该提取出 "龙江站" 或 "三明北站"
                
                # 提取站名（以"站"结尾或包含常见站名后缀）
                station_match = re.search(r'([^\s,，、。；：]+站)', station)
                if station_match:
                    potential_station = station_match.group(1)
                    # 验证是否为有效站名（2-6个字符）
                    if 2 <= len(potential_station) <= 6:
                        fixed[key] = potential_station
                        logger.info(f"站名已修复: {station} -> {potential_station}")
                
                # 如果仍然是复杂字符串，尝试提取城市名
                if len(fixed[key]) > 10:
                    # 尝试从原始城市名获取
                    city_patterns = ["福州", "厦门", "宁波", "杭州", "上海", "北京", "广州", "深圳"]
                    for city in city_patterns:
                        if city in station:
                            fixed[key] = f"{city}站"
                            break
        
        # 检查日期格式
        if "date" in fixed:
            date_str = str(fixed["date"])
            # 确保日期格式正确
            if not re.match(r"\d{4}-\d{2}-\d{2}", date_str):
                # 尝试修复
                from ..agent.time_context import parse_date_with_context
                parsed = parse_date_with_context(date_str)
                if parsed.get("parsed"):
                    fixed["date"] = parsed["parsed"]
                    logger.info(f"日期已修复: {date_str} -> {parsed['parsed']}")
        
        return fixed
    
    def _fix_weather_params(self, params: Dict) -> Dict:
        """修复天气查询参数"""
        fixed = params.copy()
        
        if "city" in fixed:
            city = str(fixed["city"])
            # 清理城市名
            city = city.strip()
            # 去除"市"、"县"等后缀（保留常见后缀如"重庆"）
            if city.endswith("市") and len(city) > 2:
                city = city[:-1]
            if city.endswith("县") and len(city) > 2:
                city = city[:-1]
            fixed["city"] = city
            
        return fixed
    
    def _fix_station_params(self, params: Dict) -> Dict:
        """修复火车站查询参数"""
        fixed = params.copy()
        
        if "city" in fixed:
            city = str(fixed["city"])
            # 清理城市名
            city = city.strip()
            # 去除"市"后缀
            if city.endswith("市") and len(city) > 2:
                city = city[:-1]
            fixed["city"] = city
            
        return fixed
    
    def _execute_with_retry(self, func: Callable, params: Dict) -> ToolResult:
        """带重试的执行"""
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                if params:
                    result = func(**params)
                else:
                    result = func()
                
                # 解析结果
                try:
                    data = json.loads(result) if isinstance(result, str) else result
                except:
                    data = {"raw": result}
                
                # 检查是否有错误
                if isinstance(data, dict):
                    if "error" in data:
                        last_error = data.get("error")
                        continue
                    
                    # 检查空结果
                    if data.get("results") == [] or data.get("count") == 0:
                        last_error = "查询结果为空"
                        continue
                
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    data=data,
                    original_params=params,
                    attempts=attempt + 1
                )
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"工具执行异常 (尝试 {attempt + 1}): {e}")
        
        return ToolResult(
            status=ToolStatus.FAILED,
            data=None,
            original_params=params,
            error=last_error,
            attempts=self.config.max_retries + 1
        )
    
    def _reflect_on_failure(self, tool_name: str, params: Dict, 
                           result: ToolResult) -> Dict:
        """
        反思失败原因，尝试修复
        
        返回：
        - should_retry: 是否应该重试
        - fixed_params: 修复后的参数
        - reason: 反思原因
        """
        reflection = {"should_retry": False, "fixed_params": None, "reason": ""}
        
        if tool_name == "get_station_by_city":
            # 火车站查询失败，尝试使用更广泛的城市名
            city = params.get("city", "")
            if city:
                # 去掉"县"等小行政单位
                if "县" in city:
                    new_city = city.replace("县", "市")
                    reflection["fixed_params"] = {"city": new_city}
                    reflection["should_retry"] = True
                    reflection["reason"] = f"尝试使用上级城市: {city} -> {new_city}"
                    
        elif tool_name == "get_train_tickets":
            # 火车票查询失败
            error_msg = result.error or ""
            
            if "无法找到出发站" in error_msg or "无法找到到达站" in error_msg:
                # 需要重新查询火车站
                reflection["should_retry"] = False
                reflection["reason"] = "需要先查询火车站信息"
                
        return reflection
    
    def _execute_fallback(self, fallback: Callable, original_tool: str, 
                          params: Dict) -> Optional[ToolResult]:
        """执行降级策略"""
        try:
            result = fallback()
            
            try:
                data = json.loads(result) if isinstance(result, str) else result
            except:
                data = {"raw": result}
            
            if isinstance(data, dict) and "error" not in data:
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    data=data,
                    original_params=params,
                    fallback_used=True
                )
                
        except Exception as e:
            logger.error(f"降级执行失败: {e}")
        
        return None


# 全局工具适配器实例
_tool_adapter: Optional[ToolAdapter] = None


def get_tool_adapter() -> ToolAdapter:
    """获取全局工具适配器"""
    global _tool_adapter
    if _tool_adapter is None:
        _tool_adapter = ToolAdapter()
    return _tool_adapter
