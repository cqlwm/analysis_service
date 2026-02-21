"""RSI 指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame
from dataclasses import dataclass

from indicators.base import BaseIndicator, IndicatorOutputProtocol, IndicatorSignal, SignalDirection


@dataclass
class RSIOutput:
    """RSI 指标输出"""
    name: str
    display_name: str
    
    rsi: float
    period: int
    overbought: float
    oversold: float
    zone: str
    
    signal: IndicatorSignal
    
    @property
    def direction(self) -> str | None:
        return self.signal["direction"]
    
    @property
    def description(self) -> str | None:
        return self.signal["description"]


class RSIIndicator(BaseIndicator):
    """RSI (Relative Strength Index) 相对强弱指标"""
    
    name = "rsi"
    display_name = "RSI"
    period = 14
    overbought = 70
    oversold = 30
    
    def calculate(self, df: DataFrame) -> DataFrame:
        close = np.asarray(df['close'].values, dtype=np.float64)
        df['rsi'] = ta.RSI(close, timeperiod=self.period)
        return df
    
    def summarize(self, df: DataFrame, latest_idx: int = -1) -> RSIOutput:
        current = df.iloc[latest_idx]
        rsi = float(current['rsi'])
        
        if rsi > self.overbought:
            direction = SignalDirection.SHORT
            zone = "overbought"
            desc = f"超买区域({rsi:.2f})，注意回调风险"
        elif rsi < self.oversold:
            direction = SignalDirection.LONG
            zone = "oversold"
            desc = f"超卖区域({rsi:.2f})，注意反弹机会"
        else:
            direction = SignalDirection.NEUTRAL
            zone = "neutral"
            desc = f"中性区域({rsi:.2f})"
        
        return RSIOutput(
            name=self.name,
            display_name=self.display_name,
            rsi=round(rsi, 2),
            period=self.period,
            overbought=self.overbought,
            oversold=self.oversold,
            zone=zone,
            signal={
                "direction": direction,
                "strength": None,
                "description": desc,
            },
        )
    
    def get_column_names(self) -> list[str]:
        return ['rsi']
