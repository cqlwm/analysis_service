"""MFI (Money Flow Index) 指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame

from indicators.base import BaseIndicator, IndicatorOutput, SignalDirection


class MFIIndicator(BaseIndicator):
    """MFI (Money Flow Index) 资金流量指标"""
    
    name = "mfi"
    display_name = "MFI"
    period = 14
    overbought = 80
    oversold = 20
    
    def calculate(self, df: DataFrame) -> DataFrame:
        high = df['high'].values.astype(np.float64)
        low = df['low'].values.astype(np.float64)
        close = df['close'].values.astype(np.float64)
        volume = df['volume'].values.astype(np.float64)
        df['mfi'] = ta.MFI(high, low, close, volume, timeperiod=self.period)
        return df
    
    def summarize(self, df: DataFrame, latest_idx: int = -1) -> IndicatorOutput:
        current = df.iloc[latest_idx]
        mfi = float(current['mfi'])
        
        if mfi > self.overbought:
            direction = SignalDirection.SHORT
            desc = f"超买区域({mfi:.2f})，资金流入可能放缓"
        elif mfi < self.oversold:
            direction = SignalDirection.LONG
            desc = f"超卖区域({mfi:.2f})，资金流出可能反转"
        elif mfi >= 50:
            direction = SignalDirection.LONG
            desc = f"资金净流入({mfi:.2f})，多头占优"
        else:
            direction = SignalDirection.SHORT
            desc = f"资金净流出({mfi:.2f})，空头占优"
        
        return {
            "name": self.name,
            "display_name": self.display_name,
            "values": {
                "mfi": round(mfi, 2),
                "period": self.period,
                "overbought": self.overbought,
                "oversold": self.oversold,
            },
            "signal": {
                "direction": direction,
                "strength": None,
                "description": desc,
            },
            "summary": f"MFI({self.period})={mfi:.2f}，{desc}",
        }
    
    def get_column_names(self) -> list[str]:
        return ['mfi']
