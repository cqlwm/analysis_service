"""Alpha Trend 指标 - 新架构适配器"""
import numpy as np
import pandas as pd
from pandas import DataFrame
from dataclasses import dataclass
import talib as ta

from indicators.base import BaseIndicator, IndicatorOutputProtocol, IndicatorSignal, SignalDirection


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


@dataclass
class AlphaTrendOutput:
    """Alpha Trend 指标输出"""
    name: str
    display_name: str
    
    at_value: float
    at_mode: str
    at_change_pct: float | None
    
    price_above_at: bool
    deviation_pct: float
    support_tests: int
    
    entry_direction: str
    bars_since_entry: int | None
    entry_price: float | None
    entry_deviation_pct: float | None
    
    exit_warning: bool
    bars_since_exit: int | None
    
    signal: IndicatorSignal
    
    @property
    def direction(self) -> str | None:
        return self.signal["direction"]
    
    @property
    def description(self) -> str | None:
        return self.signal["description"]


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
    
    def summarize(self, df: DataFrame) -> AlphaTrendOutput:
        current = df.iloc[-1]
        
        at_val = float(current[_ALPHA_TREND])
        close = float(current[_CLOSE])
        
        idx = len(df) - 1
        
        lookback = min(5, idx)
        at_series = df[_ALPHA_TREND]
        at_recent = at_series.iloc[idx - lookback: idx + 1].dropna()
        
        if len(at_recent) >= 2:
            at_start = float(at_recent.iloc[0])
            at_end = float(at_recent.iloc[-1])
            at_change_pct = round((at_end - at_start) / at_start * 100, 5)
            if abs(at_change_pct) < 0.005:
                at_mode = "flat"
            elif at_change_pct > 0:
                at_mode = "rising"
            else:
                at_mode = "falling"
        else:
            at_change_pct = None
            at_mode = "unknown"
        
        price_above_at = close > at_val
        deviation_pct = round((close - at_val) / at_val * 100, 4)
        
        entry_series = df[_TREND_SHIFT2_CROSS].iloc[:idx + 1]
        valid_entry = entry_series.dropna()
        
        if len(valid_entry) > 0:
            entry_idx = int(valid_entry.index[-1])
            entry_dir = "long" if int(valid_entry.iloc[-1]) == 1 else "short"
            bars_since_entry = idx - entry_idx
            entry_price = round(float(df.iloc[entry_idx][_CLOSE]), 6)
            entry_deviation_pct = round((close - entry_price) / entry_price * 100, 4)
        else:
            entry_dir = "none"
            bars_since_entry = None
            entry_price = None
            entry_deviation_pct = None
        
        exit_series = df[_TREND_CLOSE_CROSS].iloc[:idx + 1]
        valid_exit = exit_series.dropna()
        
        exit_warning = False
        bars_since_exit = None
        
        if len(valid_exit) > 0 and entry_dir != "none" and len(valid_entry) > 0:
            last_exit_val = int(valid_exit.iloc[-1])
            last_exit_idx = int(valid_exit.index[-1])
            last_exit_dir = "long" if last_exit_val == 1 else "short"
            
            if last_exit_idx > entry_idx:
                exit_warning = (last_exit_dir != entry_dir)
                bars_since_exit = idx - last_exit_idx
        
        test_window = 20
        start_i = max(0, idx - test_window + 1)
        test_df = df.iloc[start_i: idx + 1]
        
        if price_above_at:
            touched = (
                (test_df[_LOW] <= test_df[_ALPHA_TREND] * 1.002) &
                (test_df[_CLOSE] > test_df[_ALPHA_TREND])
            ).sum()
        else:
            touched = (
                (test_df[_HIGH] >= test_df[_ALPHA_TREND] * 0.998) &
                (test_df[_CLOSE] < test_df[_ALPHA_TREND])
            ).sum()
        
        if entry_dir == "long" and at_mode == "rising" and price_above_at:
            overall = "long"
        elif entry_dir == "short" and at_mode == "falling" and not price_above_at:
            overall = "short"
        elif at_mode == "flat":
            overall = "neutral"
        else:
            overall = "weak"
        
        desc = (
            f"AT {at_mode}，入场方向 {entry_dir}，"
            f"持续 {bars_since_entry} 根K线，"
            f"偏离入场价 {entry_deviation_pct}%，"
            f"{'退出预警激活' if exit_warning else '无退出预警'}"
        )
        
        return AlphaTrendOutput(
            name=self.name,
            display_name=self.display_name,
            at_value=round(at_val, 6),
            at_mode=at_mode,
            at_change_pct=at_change_pct,
            price_above_at=price_above_at,
            deviation_pct=deviation_pct,
            support_tests=int(touched),
            entry_direction=entry_dir,
            bars_since_entry=bars_since_entry,
            entry_price=entry_price,
            entry_deviation_pct=entry_deviation_pct,
            exit_warning=exit_warning,
            bars_since_exit=bars_since_exit,
            signal={
                "direction": overall,
                "strength": None,
                "description": desc,
            },
        )
    
    def get_column_names(self) -> list[str]:
        return [_ATR, _ATR_BASE_LOW, _ATR_BASE_HIGH, _MFI, _ALPHA_TREND, 
                _TREND_SHIFT2_CROSS, _TREND_CLOSE_CROSS]
