"""ATR (Average True Range) 指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame

from indicators.base import BaseIndicator, IndicatorOutput


class ATRIndicator(BaseIndicator):
    """ATR (Average True Range) 平均真实波幅"""
    
    name = "atr"
    display_name = "ATR"
    period = 14
    
    def calculate(self, df: DataFrame) -> DataFrame:
        high = df['high'].values.astype(np.float64)
        low = df['low'].values.astype(np.float64)
        close = df['close'].values.astype(np.float64)
        df['atr'] = ta.ATR(high, low, close, timeperiod=self.period)
        return df
    
    def summarize(self, df: DataFrame, latest_idx: int = -1) -> IndicatorOutput:
        current = df.iloc[latest_idx]
        atr = float(current['atr'])
        close = float(current['close'])
        
        # ATR是波动率指标，不直接判断方向
        atr_pct = (atr / close) * 100 if close > 0 else 0
        
        if atr_pct > 5:
            volatility = "高波动"
        elif atr_pct > 2:
            volatility = "中等波动"
        else:
            volatility = "低波动"
        
        return {
            "name": self.name,
            "display_name": self.display_name,
            "values": {
                "atr": round(atr, 6),
                "atr_percent": round(atr_pct, 2),
                "period": self.period,
            },
            "signal": {
                "direction": None,
                "strength": None,
                "description": f"ATR={atr:.4f} ({atr_pct:.2f}%)，{volatility}",
            },
            "summary": f"ATR({self.period})={atr:.4f}，{volatility}，适合设置{3*atr:.4f}为止盈幅度",
        }
    
    def get_column_names(self) -> list[str]:
        return ['atr']
