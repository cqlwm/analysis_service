"""成交量指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame
from dataclasses import dataclass

from indicators.base import BaseIndicator, IndicatorOutputProtocol, IndicatorSignal


@dataclass
class VolumeOutput:
    """成交量指标输出"""
    name: str
    display_name: str
    
    volume: float
    volume_ma: float
    ratio: float
    obv: float
    obv_slope: float
    obv_trend: str
    ma_period: int
    trend: str
    
    signal: IndicatorSignal
    
    @property
    def direction(self) -> str | None:
        return self.signal["direction"]
    
    @property
    def description(self) -> str | None:
        return self.signal["description"]


class VolumeIndicator(BaseIndicator):
    """成交量指标"""
    
    name = "volume"
    display_name = "Volume"
    ma_period = 20
    
    def calculate(self, df: DataFrame) -> DataFrame:
        close = np.asarray(df['close'].values, dtype=np.float64)
        volume = np.asarray(df['volume'].values, dtype=np.float64)
        df['volume_ma'] = ta.SMA(volume, timeperiod=self.ma_period)
        df['volume_ratio'] = volume / df['volume_ma']
        df['obv'] = ta.OBV(close, volume)
        return df
    
    def summarize(self, df: DataFrame) -> VolumeOutput:
        current = df.iloc[-1]
        volume = float(current['volume'])
        volume_ma = float(current['volume_ma'])
        volume_ratio = float(current['volume_ratio'])
        obv = float(current['obv'])

        prev_obv = float(df.iloc[-2]['obv']) if len(df) >= 2 else obv
        obv_slope = 0.0 if prev_obv == 0 else (obv - prev_obv) / abs(prev_obv) * 100

        if obv_slope > 0.2:
            obv_trend = "inflow"
        elif obv_slope < -0.2:
            obv_trend = "outflow"
        else:
            obv_trend = "flat"
        
        if volume_ratio > 1.5:
            direction = "long" if obv_trend == "inflow" else None
            trend = "surge"
            desc = f"放量({volume_ratio:.2f}x)，关注趋势延续"
        elif volume_ratio > 1.0:
            direction = "long" if obv_trend == "inflow" else None
            trend = "moderate"
            desc = f"温和放量({volume_ratio:.2f}x)"
        elif volume_ratio < 0.5:
            direction = "short" if obv_trend == "outflow" else None
            trend = "shrink"
            desc = f"缩量({volume_ratio:.2f}x)，观望"
        else:
            direction = None
            trend = "normal"
            desc = f"正常量能({volume_ratio:.2f}x)"

        if obv_trend == "inflow":
            desc = f"{desc}，OBV上行(资金净流入)"
        elif obv_trend == "outflow":
            desc = f"{desc}，OBV下行(资金净流出)"
        else:
            desc = f"{desc}，OBV走平"
        
        return VolumeOutput(
            name=self.name,
            display_name=self.display_name,
            volume=round(volume, 2),
            volume_ma=round(volume_ma, 2),
            ratio=round(volume_ratio, 2),
            obv=round(obv, 2),
            obv_slope=round(obv_slope, 4),
            obv_trend=obv_trend,
            ma_period=self.ma_period,
            trend=trend,
            signal={
                "direction": direction,
                "strength": None,
                "description": desc,
            },
        )
    
    def get_column_names(self) -> list[str]:
        return ['volume_ma', 'volume_ratio', 'obv']
