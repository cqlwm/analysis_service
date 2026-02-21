"""移动平均线指标"""
import talib as ta
import numpy as np
from pandas import DataFrame
from dataclasses import dataclass, field

from indicators.base import BaseIndicator, IndicatorOutputProtocol, IndicatorSignal, SignalDirection


@dataclass
class MAOutput:
    """移动平均线指标输出"""
    name: str
    display_name: str
    
    mas: dict[str, float]
    close: float
    period: int
    alignment: str
    price_vs_ma: str
    
    signal: IndicatorSignal
    
    @property
    def direction(self) -> str | None:
        return self.signal["direction"]
    
    @property
    def description(self) -> str | None:
        return self.signal["description"]


class MAIndicator(BaseIndicator):
    """移动平均线指标"""
    
    name = "ma"
    display_name = "Moving Average"
    periods = [20, 50, 200]
    
    def calculate(self, df: DataFrame) -> DataFrame:
        close = np.asarray(df['close'].values, dtype=np.float64)
        for period in self.periods:
            df[f'ma{period}'] = ta.SMA(close, timeperiod=period)
        return df
    
    def summarize(self, df: DataFrame) -> MAOutput:
        current = df.iloc[-1]
        close = float(current['close'])
        
        ma_values = {}
        for period in self.periods:
            ma_values[f'ma{period}'] = float(current[f'ma{period}'])
        
        ma_list = [(period, ma_values[f'ma{period}']) for period in self.periods if not np.isnan(ma_values[f'ma{period}'])]
        
        if len(ma_list) >= 2:
            sorted_asc = all(ma_list[i][1] <= ma_list[i+1][1] for i in range(len(ma_list)-1))
            sorted_desc = all(ma_list[i][1] >= ma_list[i+1][1] for i in range(len(ma_list)-1))
            
            if sorted_asc:
                direction = SignalDirection.LONG
                alignment = "bullish"
                desc = "均线多头排列，强势上涨趋势"
            elif sorted_desc:
                direction = SignalDirection.SHORT
                alignment = "bearish"
                desc = "均线空头排列，弱势下跌趋势"
            else:
                direction = SignalDirection.NEUTRAL
                alignment = "mixed"
                desc = "均线缠绕，震荡整理"
        else:
            direction = SignalDirection.NEUTRAL
            alignment = "insufficient"
            desc = "数据不足"
        
        if ma_values.get('ma20') and not np.isnan(ma_values['ma20']):
            if close > ma_values['ma20']:
                price_vs_ma = "above"
            else:
                price_vs_ma = "below"
        else:
            price_vs_ma = "unknown"
        
        ma_str = ", ".join(f"MA{p}={v:.2f}" for p, v in ma_values.items() if not np.isnan(v))
        
        return MAOutput(
            name=self.name,
            display_name=self.display_name,
            mas=ma_values,
            close=round(close, 6),
            period=max(self.periods),
            alignment=alignment,
            price_vs_ma=price_vs_ma,
            signal={
                "direction": direction,
                "strength": None,
                "description": f"{desc}，{ma_str}",
            },
        )
    
    def get_column_names(self) -> list[str]:
        return [f'ma{period}' for period in self.periods]
