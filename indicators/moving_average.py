"""移动平均线指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame

from indicators.base import BaseIndicator, IndicatorOutput, SignalDirection


class MAIndicator(BaseIndicator):
    """移动平均线指标"""
    
    name = "ma"
    display_name = "Moving Average"
    periods = [20, 50, 200]
    
    def calculate(self, df: DataFrame) -> DataFrame:
        close = df['close'].values.astype(np.float64)
        for period in self.periods:
            df[f'ma{period}'] = ta.SMA(close, timeperiod=period)
        return df
    
    def summarize(self, df: DataFrame, latest_idx: int = -1) -> IndicatorOutput:
        current = df.iloc[latest_idx]
        close = float(current['close'])
        
        # 获取各周期均线
        ma_values = {}
        for period in self.periods:
            ma_values[f'ma{period}'] = float(current[f'ma{period}'])
        
        # 判断多头/空头排列
        ma_list = [(period, ma_values[f'ma{period}']) for period in self.periods if not np.isnan(ma_values[f'ma{period}'])]
        
        if len(ma_list) >= 2:
            sorted_asc = all(ma_list[i][1] <= ma_list[i+1][1] for i in range(len(ma_list)-1))
            sorted_desc = all(ma_list[i][1] >= ma_list[i+1][1] for i in range(len(ma_list)-1))
            
            if sorted_asc:
                direction = SignalDirection.LONG
                desc = "均线多头排列，强势上涨趋势"
            elif sorted_desc:
                direction = SignalDirection.SHORT
                desc = "均线空头排列，弱势下跌趋势"
            else:
                direction = SignalDirection.NEUTRAL
                desc = "均线缠绕，震荡整理"
        else:
            direction = SignalDirection.NEUTRAL
            desc = "数据不足"
        
        # 价格与均线关系
        if ma_values.get('ma20') and not np.isnan(ma_values['ma20']):
            if close > ma_values['ma20']:
                price_vs_ma = f"价格>MA20"
            else:
                price_vs_ma = f"价格<MA20"
        else:
            price_vs_ma = ""
        
        return {
            "name": self.name,
            "display_name": self.display_name,
            "values": {**ma_values, "close": close},
            "signal": {
                "direction": direction,
                "strength": None,
                "description": f"{desc}，{price_vs_ma}",
            },
            "summary": f"MA20={ma_values.get('ma20', 'N/A'):.4f} MA50={ma_values.get('ma50', 'N/A'):.4f} MA200={ma_values.get('ma200', 'N/A'):.4f}，{desc}",
        }
    
    def get_column_names(self) -> list[str]:
        return [f'ma{period}' for period in self.periods]
