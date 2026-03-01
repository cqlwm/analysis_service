"""ATR (Average True Range) 指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame
from dataclasses import dataclass

from indicators import BaseIndicator, IndicatorSummaryOutput, IndicatorSignal


@dataclass
class ATROutput(IndicatorSummaryOutput):
    """ATR 指标输出"""
    name: str
    display_name: str
    
    atr: float
    atr_percent: float
    stop_distance: float
    stop_multiple: float
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
    stop_multiple = 1.5
    
    def calculate(self, df: DataFrame) -> DataFrame:
        high = np.asarray(df['high'].values, dtype=np.float64)
        low = np.asarray(df['low'].values, dtype=np.float64)
        close = np.asarray(df['close'].values, dtype=np.float64)
        df['atr'] = ta.ATR(high, low, close, timeperiod=self.period)
        return df
    
    def summarize(self, df: DataFrame) -> ATROutput:
        current = df.iloc[-1]
        atr = float(current['atr'])
        close = float(current['close'])
        
        atr_pct = (atr / close) * 100 if close > 0 else 0
        stop_distance = atr * self.stop_multiple
        
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
            stop_distance=round(stop_distance, 6),
            stop_multiple=self.stop_multiple,
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
