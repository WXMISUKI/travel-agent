"""
Audit Logger Module - Enterprise-grade logging system
Features:
1. Structured JSON logging
2. Execution trace tracking
3. Performance monitoring
4. Audit log querying
"""
import json
import time
import uuid
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import wraps
import threading
import os
from pathlib import Path

from .logger import logger as _logger


class AuditLevel(Enum):
    """审计级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventType(Enum):
    """事件类型"""
    USER_QUERY = "user_query"           # 用户查询
    INTENT_RECOGNITION = "intent"       # 意图识别
    ENTITY_EXTRACTION = "entity"         # 实体提取
    PLAN_CREATION = "plan_creation"     # 计划创建
    TOOL_CALL = "tool_call"             # 工具调用
    TOOL_RESULT = "tool_result"         # 工具结果
    TOOL_ERROR = "tool_error"           # 工具错误
    FALLBACK = "fallback"               # 降级
    RESPONSE_GENERATION = "response"    # 响应生成
    SESSION_START = "session_start"     # 会话开始
    SESSION_END = "session_end"         # 会话结束


@dataclass
class AuditEvent:
    """审计事件"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    event_type: str = ""
    level: str = "INFO"
    session_id: str = ""
    user_query: str = ""
    
    # 意图和实体
    intent: str = ""
    entities: Dict[str, Any] = field(default_factory=dict)
    
    # 工具信息
    tool_name: str = ""
    tool_params: Dict[str, Any] = field(default_factory=dict)
    tool_result: Any = None
    tool_error: str = ""
    
    # 执行信息
    duration_ms: float = 0
    step_id: int = 0
    
    # 额外信息
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class ExecutionTrace:
    """执行轨迹"""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: str = ""
    user_query: str = ""
    start_time: str = ""
    end_time: str = ""
    duration_ms: float = 0
    intent: str = ""
    entities: Dict[str, Any] = field(default_factory=dict)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    final_response: str = ""
    success: bool = True
    error_message: str = ""
    
    def add_step(self, step: Dict[str, Any]):
        """添加步骤"""
        self.steps.append(step)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class AuditLogger:
    """
    审计日志记录器
    
    提供：
    1. 结构化JSON日志记录
    2. 执行轨迹管理
    3. 性能指标收集
    4. 审计日志查询
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._events: List[AuditEvent] = []
        self._traces: Dict[str, ExecutionTrace] = {}
        self._current_trace: Optional[ExecutionTrace] = None
        self._session_count = 0
        self._max_events = 10000  # 内存中最大事件数
        
        # 日志目录（Vercel 仅允许 /tmp 可写）
        is_vercel = os.environ.get("VERCEL") == "1" or os.environ.get(
            "AWS_LAMBDA_FUNCTION_NAME", ""
        ).startswith("vercel-")
        self._log_dir = Path("/tmp/logs") if is_vercel else Path("logs")
        self._log_dir.mkdir(exist_ok=True)
        
        # 审计日志文件
        self._audit_file = self._log_dir / "audit.log"
        self._trace_file = self._log_dir / "traces.log"
        self._metrics_file = self._log_dir / "metrics.log"
        
        _logger.info("审计日志系统初始化完成")
    
    # ==================== 核心记录方法 ====================
    
    def log_event(self, event: AuditEvent):
        """记录审计事件"""
        # 添加到内存
        self._events.append(event)
        
        # 限制内存中事件数量
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]
        
        # 写入文件
        self._write_audit_event(event)
        
        # 输出到标准日志
        self._log_to_standard(event)
    
    def _write_audit_event(self, event: AuditEvent):
        """写入审计日志文件"""
        try:
            with open(self._audit_file, "a", encoding="utf-8") as f:
                f.write(event.to_json() + "\n")
        except Exception as e:
            _logger.error(f"写入审计日志失败: {e}")
    
    def _log_to_standard(self, event: AuditEvent):
        """输出到标准日志"""
        msg = f"[{event.event_type}] {event.tool_name or event.user_query[:50]}"
        
        if event.level == "ERROR":
            _logger.error(msg)
        elif event.level == "WARNING":
            _logger.warning(msg)
        else:
            _logger.info(msg)
    
    # ==================== 便捷方法 ====================
    
    def log_user_query(self, session_id: str, query: str, 
                       intent: str = "", entities: Dict = None):
        """记录用户查询"""
        event = AuditEvent(
            event_type=EventType.USER_QUERY.value,
            session_id=session_id,
            user_query=query,
            intent=intent,
            entities=entities or {},
            extra={"query_length": len(query)}
        )
        self.log_event(event)
        return event.event_id
    
    def log_intent_recognition(self, session_id: str, intent: str, 
                               entities: Dict, confidence: float = 1.0):
        """记录意图识别结果"""
        event = AuditEvent(
            event_type=EventType.INTENT_RECOGNITION.value,
            session_id=session_id,
            intent=intent,
            entities=entities,
            extra={"confidence": confidence}
        )
        self.log_event(event)
    
    def log_tool_call(self, session_id: str, tool_name: str, 
                      params: Dict, step_id: int = 0):
        """记录工具调用"""
        event = AuditEvent(
            event_type=EventType.TOOL_CALL.value,
            session_id=session_id,
            tool_name=tool_name,
            tool_params=self._sanitize_params(params),
            step_id=step_id
        )
        self.log_event(event)
        return event.event_id
    
    def log_tool_result(self, session_id: str, tool_name: str,
                        result: Any, duration_ms: float, 
                        event_id: str = "", error: str = ""):
        """记录工具结果"""
        event = AuditEvent(
            event_type=EventType.TOOL_RESULT.value if not error else EventType.TOOL_ERROR.value,
            session_id=session_id,
            tool_name=tool_name,
            tool_result=self._sanitize_result(result),
            tool_error=error,
            duration_ms=duration_ms,
            level="ERROR" if error else "INFO"
        )
        self.log_event(event)
    
    def log_fallback(self, session_id: str, original_tool: str,
                    fallback_tool: str, reason: str):
        """记录降级操作"""
        event = AuditEvent(
            event_type=EventType.FALLBACK.value,
            session_id=session_id,
            tool_name=original_tool,
            extra={
                "fallback_tool": fallback_tool,
                "reason": reason
            }
        )
        self.log_event(event)
    
    def log_response(self, session_id: str, response: str, 
                    success: bool = True):
        """记录响应生成"""
        event = AuditEvent(
            event_type=EventType.RESPONSE_GENERATION.value,
            session_id=session_id,
            extra={
                "response": response[:500],  # 限制长度
                "response_length": len(response),
                "success": success
            }
        )
        self.log_event(event)
    
    # ==================== 执行轨迹管理 ====================
    
    def start_trace(self, session_id: str, user_query: str) -> ExecutionTrace:
        """开始执行轨迹"""
        self._session_count += 1
        trace = ExecutionTrace(
            session_id=session_id,
            user_query=user_query,
            start_time=datetime.now().isoformat()
        )
        self._traces[trace.trace_id] = trace
        self._current_trace = trace
        
        # 记录会话开始
        event = AuditEvent(
            event_type=EventType.SESSION_START.value,
            session_id=session_id,
            user_query=user_query,
            extra={"trace_id": trace.trace_id}
        )
        self.log_event(event)
        
        _logger.info(f"开始执行轨迹: {trace.trace_id}, 会话: {session_id}")
        return trace
    
    def end_trace(self, trace_id: str, success: bool = True, 
                  error_message: str = "", final_response: str = ""):
        """结束执行轨迹"""
        if trace_id not in self._traces:
            _logger.warning(f"轨迹不存在: {trace_id}")
            return
        
        trace = self._traces[trace_id]
        trace.end_time = datetime.now().isoformat()
        trace.success = success
        trace.error_message = error_message
        trace.final_response = final_response
        
        # 计算总时长
        if trace.start_time:
            start = datetime.fromisoformat(trace.start_time)
            end = datetime.fromisoformat(trace.end_time)
            trace.duration_ms = (end - start).total_seconds() * 1000
        
        # 写入轨迹文件
        self._write_trace(trace)
        
        # 记录会话结束
        event = AuditEvent(
            event_type=EventType.SESSION_END.value,
            session_id=trace.session_id,
            extra={
                "trace_id": trace_id,
                "duration_ms": trace.duration_ms,
                "success": success,
                "step_count": len(trace.steps)
            }
        )
        self.log_event(event)
        
        # 记录性能指标
        self._record_metrics(trace)
        
        _logger.info(f"结束执行轨迹: {trace_id}, 耗时: {trace.duration_ms:.2f}ms, 成功: {success}")
        
        self._current_trace = None
    
    def add_trace_step(self, trace_id: str, step: Dict):
        """添加轨迹步骤"""
        if trace_id in self._traces:
            self._traces[trace_id].add_step(step)
    
    def _write_trace(self, trace: ExecutionTrace):
        """写入轨迹文件"""
        try:
            with open(self._trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            _logger.error(f"写入轨迹失败: {e}")
    
    def _record_metrics(self, trace: ExecutionTrace):
        """记录性能指标"""
        try:
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "trace_id": trace.trace_id,
                "session_id": trace.session_id,
                "intent": trace.intent,
                "duration_ms": trace.duration_ms,
                "step_count": len(trace.steps),
                "success": trace.success,
                "error_message": trace.error_message
            }
            
            with open(self._metrics_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(metrics, ensure_ascii=False) + "\n")
        except Exception as e:
            _logger.error(f"记录指标失败: {e}")
    
    # ==================== 性能监控装饰器 ====================
    
    def monitor(self, operation_name: str = ""):
        """性能监控装饰器"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                operation = operation_name or func.__name__
                
                try:
                    result = func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000
                    
                    # 记录成功
                    _logger.debug(f"{operation} 完成, 耗时: {duration_ms:.2f}ms")
                    
                    return result
                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    
                    # 记录错误
                    _logger.error(f"{operation} 失败, 耗时: {duration_ms:.2f}ms, 错误: {str(e)}")
                    
                    raise
            
            return wrapper
        return decorator
    
    # ==================== 查询接口 ====================
    
    def query_events(self, 
                    session_id: str = None,
                    event_type: str = None,
                    tool_name: str = None,
                    level: str = None,
                    start_time: str = None,
                    end_time: str = None,
                    limit: int = 100) -> List[Dict]:
        """查询审计事件"""
        results = []
        
        for event in reversed(self._events):
            # 过滤条件
            if session_id and event.session_id != session_id:
                continue
            if event_type and event.event_type != event_type:
                continue
            if tool_name and event.tool_name != tool_name:
                continue
            if level and event.level != level:
                continue
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            
            results.append(event.to_dict())
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_session_summary(self, session_id: str) -> Dict:
        """获取会话摘要"""
        events = self.query_events(session_id=session_id, limit=1000)
        
        tool_calls = [e for e in events if e["event_type"] == EventType.TOOL_CALL.value]
        tool_errors = [e for e in events if e["event_type"] == EventType.TOOL_ERROR.value]
        fallbacks = [e for e in events if e["event_type"] == EventType.FALLBACK.value]
        
        # 计算平均工具调用时间
        tool_results = [e for e in events if e["event_type"] == EventType.TOOL_RESULT.value]
        durations = [e["duration_ms"] for e in tool_results if e.get("duration_ms", 0) > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "session_id": session_id,
            "event_count": len(events),
            "tool_calls": len(tool_calls),
            "tool_errors": len(tool_errors),
            "fallbacks": len(fallbacks),
            "avg_tool_duration_ms": avg_duration,
            "first_event": events[-1]["timestamp"] if events else None,
            "last_event": events[0]["timestamp"] if events else None
        }
    
    def get_metrics_summary(self, hours: int = 24) -> Dict:
        """获取性能指标摘要"""
        start_time = datetime.now() - timedelta(hours=hours)
        start_str = start_time.isoformat()
        
        metrics = []
        try:
            with open(self._metrics_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        m = json.loads(line)
                        if m.get("timestamp", "") >= start_str:
                            metrics.append(m)
                    except:
                        continue
        except FileNotFoundError:
            pass
        
        if not metrics:
            return {
                "period_hours": hours,
                "total_requests": 0,
                "success_rate": 0,
                "avg_duration_ms": 0
            }
        
        total = len(metrics)
        successes = sum(1 for m in metrics if m.get("success", True))
        durations = [m.get("duration_ms", 0) for m in metrics if m.get("duration_ms", 0) > 0]
        
        return {
            "period_hours": hours,
            "total_requests": total,
            "success_count": successes,
            "success_rate": successes / total * 100 if total > 0 else 0,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "min_duration_ms": min(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "error_count": total - successes
        }
    
    # ==================== 工具方法 ====================
    
    def _sanitize_params(self, params: Dict) -> Dict:
        """清理敏感参数"""
        sanitized = {}
        sensitive_keys = ["api_key", "password", "token", "secret"]
        
        for k, v in params.items():
            if any(s in k.lower() for s in sensitive_keys):
                sanitized[k] = "***"
            else:
                sanitized[k] = v
        
        return sanitized
    
    def _sanitize_result(self, result: Any) -> Any:
        """清理结果数据"""
        if isinstance(result, dict):
            # 限制大小
            if len(str(result)) > 2000:
                return {"_truncated": True, "_length": len(str(result))}
            return result
        return result
    
    def get_current_trace(self) -> Optional[ExecutionTrace]:
        """获取当前执行轨迹"""
        return self._current_trace
    
    def clear_old_events(self, days: int = 7):
        """清理旧事件"""
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        
        original_count = len(self._events)
        self._events = [e for e in self._events if e.timestamp >= cutoff_str]
        
        removed = original_count - len(self._events)
        _logger.info(f"清理了 {removed} 条旧审计事件")


# 全局审计日志实例
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志实例"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# 便捷函数
def audit_log_event(**kwargs):
    """便捷的日志记录"""
    event = AuditEvent(**kwargs)
    get_audit_logger().log_event(event)


def audit_monitor(operation_name: str = ""):
    """便捷的性能监控装饰器"""
    return get_audit_logger().monitor(operation_name)
