"""复合策略 - 组合多个指标进行综合分析"""
from pandas import DataFrame
from typing import TypedDict

from indicators import IndicatorRegistry, IndicatorOutput


class StrategySummary(TypedDict):
    """策略汇总输出"""
    indicators: list[IndicatorOutput]
    latest_price: float
    latest_time: str


class CompositeStrategy:
    """
    复合策略 - 支持插件式指标组合
    
    用法:
        strategy = CompositeStrategy()  # 使用所有注册指标
        strategy = CompositeStrategy(indicator_names=['rsi', 'macd'])  # 指定指标
    """
    
    def __init__(self, indicator_names: list[str] | None = None):
        """
        初始化复合策略
        
        Args:
            indicator_names: 指定要使用的指标名称列表，None表示使用所有已注册指标
        """
        # 确保指标已注册
        IndicatorRegistry.initialize()
        
        if indicator_names:
            self.indicators = [IndicatorRegistry.get(name) for name in indicator_names]
            self.indicators = [ind for ind in self.indicators if ind is not None]
            if len(self.indicators) != len(indicator_names):
                missing = set(indicator_names) - set(IndicatorRegistry.names())
                raise ValueError(f"未找到指标: {missing}")
        else:
            self.indicators = IndicatorRegistry.all()
    
    def calculate_all(self, df: DataFrame) -> DataFrame:
        """
        计算所有指标
        
        Args:
            df: OHLCV数据
            
        Returns:
            添加了所有指标列的DataFrame
        """
        for indicator in self.indicators:
            df = indicator.calculate(df)
        return df
    
    def generate_summary(self, df: DataFrame, latest_idx: int = -1) -> StrategySummary:
        """
        生成所有指标的摘要
        
        Args:
            df: 已计算指标的DataFrame
            latest_idx: 最新数据索引
            
        Returns:
            包含所有指标摘要的汇总
        """
        summaries = []
        for indicator in self.indicators:
            try:
                summary = indicator.summarize(df, latest_idx)
                summaries.append(summary)
            except Exception as e:
                # 跳过计算失败的指标
                pass
        
        return {
            "indicators": summaries,
            "latest_price": float(df.iloc[latest_idx]['close']),
            "latest_time": str(df.iloc[latest_idx].get('datetime', '')),
        }
    
    def get_all_column_names(self) -> list[str]:
        """获取所有指标生成的列名"""
        columns = []
        for indicator in self.indicators:
            columns.extend(indicator.get_column_names())
        return columns
    
    @property
    def indicator_names(self) -> list[str]:
        """获取当前策略使用的指标名称"""
        return [ind.name for ind in self.indicators]
