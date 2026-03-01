"""布林带指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame
from dataclasses import dataclass

from indicators import BaseIndicator, SignalDirection, IndicatorSummaryOutput, IndicatorSignal


@dataclass
class BollingerOutput(IndicatorSummaryOutput):
    """布林带指标输出"""
    name: str
    display_name: str
    
    upper: float
    middle: float
    lower: float
    position: float
    bandwidth_pct: float
    squeeze_state: str
    period: int
    std_dev: float
    zone: str
    
    signal: IndicatorSignal
    
    @property
    def direction(self) -> str | None:
        return self.signal["direction"]
    
    @property
    def description(self) -> str | None:
        return self.signal["description"]


class BollingerBandsIndicator(BaseIndicator):
    """布林带 (Bollinger Bands) 指标"""
    
    name = "bollinger"
    display_name = "Bollinger Bands"
    period = 20
    std_dev = 2
    
    def calculate(self, df: DataFrame) -> DataFrame:
        close = np.asarray(df['close'].values, dtype=np.float64)
        upper, middle, lower = ta.BBANDS(
            close,
            timeperiod=self.period,
            nbdevup=self.std_dev,
            nbdevdn=self.std_dev
        )
        df['bb_upper'] = upper
        df['bb_middle'] = middle
        df['bb_lower'] = lower
        return df
    
    def summarize(self, df: DataFrame) -> BollingerOutput:
        current = df.iloc[-1]
        close = float(current['close'])
        bb_upper = float(current['bb_upper'])
        bb_middle = float(current['bb_middle'])
        bb_lower = float(current['bb_lower'])

        position = (close - bb_lower) / (bb_upper - bb_lower) * 100 if bb_upper != bb_lower else 50
        bandwidth_pct = ((bb_upper - bb_lower) / bb_middle) * 100 if bb_middle != 0 else 0

        if bandwidth_pct < 4:
            squeeze_state = "compressed"
        elif bandwidth_pct > 10:
            squeeze_state = "expanded"
        else:
            squeeze_state = "normal"
        
        if close > bb_upper:
            direction = SignalDirection.SHORT
            zone = "above_upper"
            desc = f"突破上轨({bb_upper:.4f})，超买信号"
        elif close < bb_lower:
            direction = SignalDirection.LONG
            zone = "below_lower"
            desc = f"跌破下轨({bb_lower:.4f})，超卖信号"
        elif position > 80:
            direction = SignalDirection.SHORT
            zone = "near_upper"
            desc = f"接近上轨({position:.0f}%)，注意回调"
        elif position < 20:
            direction = SignalDirection.LONG
            zone = "near_lower"
            desc = f"接近下轨({position:.0f}%)，注意反弹"
        else:
            direction = SignalDirection.NEUTRAL
            zone = "middle"
            desc = f"布林带中轨附近({position:.0f}%)"
        
        return BollingerOutput(
            name=self.name,
            display_name=self.display_name,
            upper=round(bb_upper, 6),
            middle=round(bb_middle, 6),
            lower=round(bb_lower, 6),
            position=round(position, 2),
            bandwidth_pct=round(bandwidth_pct, 4),
            squeeze_state=squeeze_state,
            period=self.period,
            std_dev=self.std_dev,
            zone=zone,
            signal={
                "direction": direction,
                "strength": None,
                "description": desc,
            },
        )
    
    def get_column_names(self) -> list[str]:
        return ['bb_upper', 'bb_middle', 'bb_lower']
