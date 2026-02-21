"""解释器模块 - 将结构化指标数据转换为LLM易懂的自然语言"""
from abc import ABC, abstractmethod
from typing import TypedDict


class InterpreterOutput(TypedDict):
    """解释器输出"""
    summary: str  # 自然语言描述，供LLM理解
    analysis: str  # 深度分析


class BaseInterpreter(ABC):
    """解释器基类 - 负责将指标的结构化数据转换为自然语言"""
    
    indicator_name: str = ""  # 对应的指标名称
    
    @abstractmethod
    def interpret(self, values: dict[str, float], signal: dict | None) -> InterpreterOutput:
        """
        解释指标数据
        
        Args:
            values: 指标的结构化数值
            signal: 指标信号 (direction, strength, description)
            
        Returns:
            包含summary和analysis的自然语言输出
        """
        pass


class InterpreterRegistry:
    """解释器注册中心"""
    
    _interpreters: dict[str, BaseInterpreter] = {}
    
    @classmethod
    def register(cls, interpreter: BaseInterpreter) -> None:
        cls._interpreters[interpreter.indicator_name] = interpreter
    
    @classmethod
    def get(cls, indicator_name: str) -> BaseInterpreter | None:
        return cls._interpreters.get(indicator_name)
    
    @classmethod
    def all(cls) -> list[BaseInterpreter]:
        return list(cls._interpreters.values())
    
    @classmethod
    def names(cls) -> list[str]:
        return list(cls._interpreters.keys())


class DefaultInterpreter(BaseInterpreter):
    """默认解释器 - 当没有专门解释器时使用"""
    
    indicator_name = "_default"
    
    def interpret(self, values: dict[str, float], signal: dict | None) -> InterpreterOutput:
        # 简单拼接所有值
        value_str = ", ".join(f"{k}={v}" for k, v in values.items())
        
        signal_info = ""
        if signal and signal.get('direction'):
            signal_info = f" 信号方向: {signal['direction']}"
        
        return {
            "summary": f"{value_str}{signal_info}",
            "analysis": f"当前指标值为 {value_str}，{signal_info or '无明确方向'}",
        }
