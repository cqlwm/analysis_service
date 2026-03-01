"""解释器模块 - 将结构化指标数据转换为LLM易懂的自然语言"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypedDict, TypeVar, Generic


@dataclass
class IndicatorSummaryOutput:
    """指标摘要输出基类 - 作为 interpret 方法的入口类型"""
    pass


T = TypeVar('T', bound=IndicatorSummaryOutput)


class InterpreterOutput(TypedDict):
    """解释器输出"""
    analysis: str  # 深度分析


class BaseInterpreter(Generic[T], ABC):
    """解释器基类 - 负责将指标的结构化数据转换为自然语言"""
    
    indicator_name: str = ""
    
    @abstractmethod
    def interpret(self, indicator_summary: T) -> InterpreterOutput:
        """
        解释指标数据
        
        Args:
            indicator_summary: 指标的结构化数值
            
        Returns:
            包含analysis的自然语言输出
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


class DefaultInterpreter(BaseInterpreter[IndicatorSummaryOutput]):
    """默认解释器 - 当没有专门解释器时使用"""
    
    indicator_name = "_default"
    
    def interpret(self, indicator_summary: IndicatorSummaryOutput) -> InterpreterOutput:
        value_str = str(indicator_summary.__dict__)
        
        return {
            "analysis": f"当前指标值为 {value_str}",
        }
