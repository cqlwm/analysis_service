"""布林带指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame

from indicators.base import BaseIndicator, IndicatorOutput, SignalDirection


class BollingerBandsIndicator(BaseIndicator):
    """布林带 (Bollinger Bands) 指标"""
    
    name = "bollinger"
    display_name = "Bollinger Bands"
    period = 20
    std_dev = 2
    
    def calculate(self, df: DataFrame) -> DataFrame:
        close = df['close'].values.astype(np.float64)
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
    
    def summarize(self, df: DataFrame, latest_idx: int = -1) -> IndicatorOutput:
        current = df.iloc[latest_idx]
        close = float(current['close'])
        bb_upper = float(current['bb_upper'])
        bb_middle = float(current['bb_middle'])
        bb_lower = float(current['bb_lower'])
        
        # 计算价格在布林带中的位置
        position = (close - bb_lower) / (bb_upper - bb_lower) * 100 if bb_upper != bb_lower else 50
        
        if close > bb_upper:
            direction = SignalDirection.SHORT
            desc = f"突破上轨({bb_upper:.4f})，超买信号"
        elif close < bb_lower:
            direction = SignalDirection.LONG
            desc = f"跌破下轨({bb_lower:.4f})，超卖信号"
        elif position > 80:
            direction = SignalDirection.SHORT
            desc = f"接近上轨({position:.0f}%)，注意回调"
        elif position < 20:
            direction = SignalDirection.LONG
            desc = f"接近下轨({position:.0f}%)，注意反弹"
        else:
            direction = SignalDirection.NEUTRAL
            desc = f"布林带中轨附近({position:.0f}%)"
        
        return {
            "name": self.name,
            "display_name": self.display_name,
            "values": {
                "bb_upper": round(bb_upper, 6),
                "bb_middle": round(bb_middle, 6),
                "bb_lower": round(bb_lower, 6),
                "bb_position": round(position, 2),
                "period": self.period,
                "std_dev": self.std_dev,
            },
            "signal": {
                "direction": direction,
                "strength": None,
                "description": desc,
            },
            "summary": f"BB({self.period})=上:{bb_upper:.4f} 中:{bb_middle:.4f} 下:{bb_lower:.4f}，{desc}",
        }
    
    def get_column_names(self) -> list[str]:
        return ['bb_upper', 'bb_middle', 'bb_lower']
