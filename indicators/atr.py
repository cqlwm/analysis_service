"""ATR (Average True Range) 指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame
from dataclasses import dataclass

from indicators.base import BaseIndicator, IndicatorOutputProtocol, IndicatorSignal


@dataclass
class ATROutput:
    """ATR 指标输出"""
    name: str
    display_name: str
    
    atr: float
    atr_percent: float
    period: int
    volatility: str
    
    signal: IndicatorSignal
    
    @property
    def direction(self) -> str | None:
        return self.signal["direction"]
    
    @property
    def description(self) -> str | None:
        return self.signal["description"]


class ATRIndicator(BaseIndicator):
    """ATR (Average True Range) 平均真实波幅"""
    
    name = "atr"
    display_name = "ATR"
    period = 14
    
    def calculate(self, df: DataFrame) -> DataFrame:
        high = np.asarray(df['high'].values, dtype=np.float64)
        low = np.asarray(df['low'].values, dtype=np.float64)
        close = np.asarray(df['close'].values, dtype=np.float64)
        df['atr'] = ta.ATR(high, low, close, timeperiod=self.period)
        return df
    
    def summarize(self, df: DataFrame, latest_idx: int = -1) -> ATROutput:
        current = df.iloc[latest_idx]
        atr = float(current['atr'])
        close = float(current['close'])
        
        atr_pct = (atr / close) * 100 if close > 0 else 0
        
        if atr_pct > 5:
            volatility = "high"
            volatility_desc = "高波动"
        elif atr_pct > 2:
            volatility = "medium"
            volatility_desc = "中等波动"
        else:
            volatility = "low"
            volatility_desc = "低波动"
        
        return ATROutput(
            name=self.name,
            display_name=self.display_name,
            atr=round(atr, 6),
            atr_percent=round(atr_pct, 2),
            period=self.period,
            volatility=volatility,
            signal={
                "direction": None,
                "strength": None,
                "description": f"ATR={atr:.4f} ({atr_pct:.2f}%)，{volatility_desc}",
            },
        )
    
    def get_column_names(self) -> list[str]:
        return ['atr']
