"""指标模块基类定义"""
from abc import ABC, abstractmethod

from pandas import DataFrame
from typing import Protocol, TypedDict

class IndicatorSummaryOutput(Protocol):
    """指标输出协议 - 所有 Output 类必须实现此接口"""
    name: str
    display_name: str


class IndicatorSignal(TypedDict):
    direction: str | None
    strength: float | None
    description: str | None

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
    def summarize(self, df: DataFrame) -> IndicatorSummaryOutput:
        """
        提取指标摘要

        Args:
            df: 已计算指标的DataFrame

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
