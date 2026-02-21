"""成交量指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame

from indicators.base import BaseIndicator, IndicatorOutput, SignalDirection


class VolumeIndicator(BaseIndicator):
    """成交量指标"""
    
    name = "volume"
    display_name = "Volume"
    ma_period = 20
    
    def calculate(self, df: DataFrame) -> DataFrame:
        volume = df['volume'].values.astype(np.float64)
        df['volume_ma'] = ta.SMA(volume, timeperiod=self.ma_period)
        df['volume_ratio'] = volume / df['volume_ma']
        return df
    
    def summarize(self, df: DataFrame, latest_idx: int = -1) -> IndicatorOutput:
        current = df.iloc[latest_idx]
        volume = float(current['volume'])
        volume_ma = float(current['volume_ma'])
        volume_ratio = float(current['volume_ratio'])
        
        if volume_ratio > 1.5:
            direction = None  # 成交量放大不直接预示方向
            desc = f"放量({volume_ratio:.2f}x)，关注趋势延续"
        elif volume_ratio > 1.0:
            direction = None
            desc = f"温和放量({volume_ratio:.2f}x)"
        elif volume_ratio < 0.5:
            direction = None
            desc = f"缩量({volume_ratio:.2f}x)，观望"
        else:
            direction = None
            desc = f"正常量能({volume_ratio:.2f}x)"
        
        return {
            "name": self.name,
            "display_name": self.display_name,
            "values": {
                "volume": round(volume, 2),
                "volume_ma": round(volume_ma, 2),
                "volume_ratio": round(volume_ratio, 2),
                "ma_period": self.ma_period,
            },
            "signal": {
                "direction": direction,
                "strength": None,
                "description": desc,
            },
            "summary": f"成交量={volume:.0f} MA{self.ma_period}={volume_ma:.0f} 比率={volume_ratio:.2f}x，{desc}",
        }
    
    def get_column_names(self) -> list[str]:
        return ['volume_ma', 'volume_ratio']
