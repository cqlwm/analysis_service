"""Alpha Trend 指标 - 新架构适配器"""
import numpy as np
import pandas as pd
from pandas import DataFrame
from typing import TypedDict
import talib as ta

from indicators.base import BaseIndicator, IndicatorOutput, SignalDirection


# 常量定义
_HIGH = 'high'
_LOW = 'low'
_CLOSE = 'close'
_VOLUME = 'volume'
_ATR = 'atr'
_ATR_BASE_LOW = 'atr_base_low'
_ATR_BASE_HIGH = 'atr_base_high'
_MFI = 'mfi'
_ALPHA_TREND = 'alpha_trend'
_TREND_SHIFT2_CROSS = 'alpha_trend_shift2_cross_signal'
_TREND_CLOSE_CROSS = 'alpha_trend_close_cross_signal'


class AlphaTrendIndicator(BaseIndicator):
    """
    Alpha Trend 指标
    
    策略逻辑：
    1. 使用Alpha Trend作为主趋势指标
    2. 结合MFI判断资金流向
    3. 动态生成交易信号
    """
    
    name = "alpha_trend"
    display_name = "Alpha Trend"
    atr_multiple = 1.0
    period = 8
    
    def calculate(self, df: DataFrame) -> DataFrame:
        df = df.copy()
        
        high_values = df[_HIGH].values.astype(np.float64)
        low_values = df[_LOW].values.astype(np.float64)
        close_values = df[_CLOSE].values.astype(np.float64)
        volume_values = df[_VOLUME].values.astype(np.float64)
        
        # 计算ATR
        atr_values = ta.ATR(high_values, low_values, close_values, timeperiod=self.period)
        atr_range_values = atr_values * self.atr_multiple
        atr_base_low_values = low_values - atr_range_values
        atr_base_high_values = high_values + atr_range_values
        mfi_values = ta.MFI(high_values, low_values, close_values, volume_values, timeperiod=self.period)
        
        df[_ATR] = atr_values
        df[_ATR_BASE_LOW] = atr_base_low_values
        df[_ATR_BASE_HIGH] = atr_base_high_values
        df[_MFI] = mfi_values
        
        # 计算Alpha Trend
        alpha_trend_values = np.full(len(df), np.nan)
        if self.period < len(df):
            alpha_trend_values[self.period] = (
                atr_base_low_values[self.period] 
                if mfi_values[self.period] >= 50 
                else atr_base_high_values[self.period]
            )
            
            for i in range(self.period + 1, len(df)):
                if mfi_values[i] >= 50:
                    alpha_trend_values[i] = max(alpha_trend_values[i-1], atr_base_low_values[i])
                else:
                    alpha_trend_values[i] = min(alpha_trend_values[i-1], atr_base_high_values[i])
        
        df[_ALPHA_TREND] = alpha_trend_values
        
        # 计算交叉信号
        alpha_trend_shift2 = df[_ALPHA_TREND].shift(2)
        df[_TREND_SHIFT2_CROSS] = np.select(
            [
                (df[_ALPHA_TREND] > alpha_trend_shift2).astype(bool),
                (df[_ALPHA_TREND] < alpha_trend_shift2).astype(bool)
            ],
            [1, -1],
            default=np.nan
        )
        
        close_shift = df[_CLOSE].shift(1)
        alpha_trend_shift = df[_ALPHA_TREND].shift(1)
        df[_TREND_CLOSE_CROSS] = np.select(
            [
                (df[_CLOSE] > df[_ALPHA_TREND]) & (close_shift <= alpha_trend_shift),
                (df[_CLOSE] < df[_ALPHA_TREND]) & (close_shift >= alpha_trend_shift)
            ],
            [1, -1],
            default=np.nan
        )
        
        # 去重信号
        df.reset_index(drop=True, inplace=True)
        current_signal = None
        for i in range(len(df)):
            sig = df.at[i, _TREND_SHIFT2_CROSS]
            if pd.notna(sig):
                if sig == current_signal:
                    df.at[i, _TREND_SHIFT2_CROSS] = np.nan
                else:
                    current_signal = sig
            
            trend_close_cross_signal = df.at[i, _TREND_CLOSE_CROSS]
            if pd.notna(trend_close_cross_signal):
                if trend_close_cross_signal == current_signal:
                    df.at[i, _TREND_CLOSE_CROSS] = np.nan
        
        return df
    
    def summarize(self, df: DataFrame, latest_idx: int = -1) -> IndicatorOutput:
        current = df.iloc[latest_idx]
        
        alpha_trend = float(current[_ALPHA_TREND])
        close = float(current[_CLOSE])
        signal_val = current[_TREND_SHIFT2_CROSS]
        
        # 判断信号方向
        if pd.notna(signal_val):
            direction = SignalDirection.LONG if signal_val == 1 else SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL

        price_vs_at = (close - alpha_trend) / close * 100
        
        # 获取最近的有效信号
        signal_series = df[_TREND_SHIFT2_CROSS]
        valid_signals = signal_series.dropna()
        
        if len(valid_signals) > 0:
            last_signal_idx = int(valid_signals.last_valid_index())
            kline_count_since_signal = len(df) - last_signal_idx
            signal_price = float(df.iloc[last_signal_idx][_CLOSE])
            deviation = (close - signal_price) / signal_price * 100
        else:
            kline_count_since_signal = 0
            signal_price = close
            deviation = 0
        
        desc = f"{price_vs_at}，{'多头' if direction == SignalDirection.LONG else '空头' if direction == SignalDirection.SHORT else '中性'}信号"
        
        return {
            "name": self.name,
            "display_name": self.display_name,
            "values": {
                "alpha_trend": round(alpha_trend, 6),
                "atr": round(float(current[_ATR]), 6),
                "mfi": round(float(current[_MFI]), 2),
                "signal": int(signal_val) if pd.notna(signal_val) else 0,
                "kline_count_since_signal": kline_count_since_signal,
                "price_deviation_from_signal": round(deviation, 2),
            },
            "signal": {
                "direction": direction,
                "strength": None,
                "description": desc,
            },
        }
    
    def get_column_names(self) -> list[str]:
        return [_ATR, _ATR_BASE_LOW, _ATR_BASE_HIGH, _MFI, _ALPHA_TREND, 
                _TREND_SHIFT2_CROSS, _TREND_CLOSE_CROSS]
