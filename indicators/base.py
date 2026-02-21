"""指标模块基类定义"""
from abc import ABC, abstractmethod
from pandas import DataFrame
from typing import TypedDict


class IndicatorValue(TypedDict):
    """指标单值输出"""
    key: str
    value: float


class IndicatorSignal(TypedDict):
    """指标信号"""
    direction: str | None  # "long", "short", None
    strength: float | None  # 0-100
    description: str


class IndicatorOutput(TypedDict):
    """指标完整输出 - 仅包含结构化数据，不包含自然语言描述"""
    name: str
    display_name: str
    values: dict[str, float]
    signal: IndicatorSignal | None


class BaseIndicator(ABC):
    """指标基类，所有指标需继承此类"""
    
    name: str = ""  # 标识符，如 "rsi", "macd"
    display_name: str = ""  # 显示名称，如 "RSI", "MACD"
    
    @abstractmethod
    def calculate(self, df: DataFrame) -> DataFrame:
        """
        计算指标并添加到DataFrame
        
        Args:
            df: 包含OHLCV数据的DataFrame
            
        Returns:
            添加了指标列的DataFrame
        """
        pass
    
    @abstractmethod
    def summarize(self, df: DataFrame, latest_idx: int = -1) -> IndicatorOutput:
        """
        提取指标摘要
        
        Args:
            df: 已计算指标的DataFrame
            latest_idx: 最新数据的索引，默认-1
            
        Returns:
            包含值、信号、摘要的结构化输出
        """
        pass
    
    def get_column_names(self) -> list[str]:
        """获取指标生成的列名，供其他模块使用"""
        return []


class SignalDirection:
    """信号方向常量"""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
