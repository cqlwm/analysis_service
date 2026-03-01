"""Alpha Trend 指标 - 新架构适配器"""
import numpy as np
import pandas as pd
from pandas import DataFrame
from dataclasses import dataclass
import talib as ta

from indicators import BaseIndicator, IndicatorSummaryOutput
from utils import get_decimal_places, truncate_decimal

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
class ExitTest:
    at_val: float
    close_price: float


@dataclass
class AlphaTrendOutput(IndicatorSummaryOutput):
    """Alpha Trend 指标输出"""
    name: str
    display_name: str
    
    at_value: float
    at_mode: str
    at_change_pct: float | None
    
    price_above_at: bool
    deviation_pct: float

    entry_direction: str
    bars_since_entry: int | None
    entry_price: float | None
    entry_deviation_pct: float | None
    
    exit_warning: bool
    bars_since_exit: int | None
    exit_tests: list[ExitTest]

    overall: str

    # 增强字段
    high_since_signal: float | None = None
    low_since_signal: float | None = None
    high_since_kline_count: int | None = None
    low_since_kline_count: int | None = None
    max_drawdown: float | None = None
    key_alpha_values: list[float] | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None


def _find_recent_consecutive_alpha_trend(alpha_trend_values: np.ndarray, current_index: int) -> float | None:
    """Find recent consecutive alpha trend values for stop loss reference"""
    for i in range(current_index - 2, -1, -1):
        if not np.isnan(alpha_trend_values[i]) and i >= 2:
            if alpha_trend_values[i] == alpha_trend_values[i + 1] == alpha_trend_values[i + 2]:
                return float(alpha_trend_values[i])
    return None


def _calculate_clustered_support_resistance(curr_price: float, segments: list[dict[str, float]]) -> dict[str, list[float]]:
    """Calculate support and resistance levels from segments"""
    if not segments:
        return {'support': [], 'resistance': []}

    price_levels: set[float] = set()
    for segment in segments:
        price_levels.update([segment['high_price'], segment['low_price'], segment['alpha_trend']])

    support = [p for p in price_levels if not np.isnan(p) and p <= curr_price]
    support.sort(reverse=True)

    resistance = [p for p in price_levels if not np.isnan(p) and p > curr_price]
    resistance.sort()

    return {
        'support': support,
        'resistance': resistance,
    }


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
    at_lookback_period = 5
    pct_places = 4
    
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
        df = df.reset_index(drop=True, inplace=False)

        last_idx = len(df) - 1

        last_row = df.iloc[last_idx]
        at_val = float(last_row[_ALPHA_TREND])
        close = float(last_row[_CLOSE])
        high = float(last_row[_HIGH])
        low = float(last_row[_LOW])

        price_places = get_decimal_places((close + high) / 2)

        lookback = min(self.at_lookback_period, last_idx)
        at_series = df[_ALPHA_TREND]
        at_recent = at_series.iloc[last_idx - lookback: last_idx + 1].dropna()
        
        if len(at_recent) >= 2:
            at_start = float(at_recent.iloc[0])
            at_end = float(at_recent.iloc[-1])
            at_change_pct = round((at_end - at_start) / at_start * 100, self.pct_places)
            if abs(at_change_pct) < 0.01:
                at_mode = "flat"
            elif at_change_pct > 0:
                at_mode = "rising"
            else:
                at_mode = "falling"
        else:
            at_change_pct = None
            at_mode = "unknown"
        
        price_above_at = close > at_val
        deviation_pct = round((close - at_val) / at_val * 100, self.pct_places)
        
        valid_entry = df[_TREND_SHIFT2_CROSS].dropna()
        
        entry_idx = None
        if len(valid_entry) > 0:
            entry_idx = int(valid_entry.index[-1])
            entry_dir = "long" if int(valid_entry.iloc[-1]) == 1 else "short"
            bars_since_entry = last_idx - entry_idx
            entry_price = float(df.iloc[entry_idx][_CLOSE])
            entry_deviation_pct = round((close - entry_price) / entry_price * 100, self.pct_places)
        else:
            entry_dir = "none"
            bars_since_entry = None
            entry_price = None
            entry_deviation_pct = None
        
        exit_warning = False
        bars_since_exit = None
        exit_tests = []

        if entry_idx:
            valid_exit = df[_TREND_CLOSE_CROSS].dropna()
            for i in range(1, len(valid_exit) + 1):
                exit_idx = int(valid_exit.index[-i])
                if exit_idx > entry_idx:
                    exit_tests.append(ExitTest(
                        at_val=float(df[_ALPHA_TREND][exit_idx]),
                        close_price=float(df[_CLOSE][exit_idx]),
                    ))
                else:
                    break

            if len(valid_entry) > 0 and entry_dir != "none" and len(valid_entry) > 0:
                last_exit_val = int(valid_exit.iloc[-1])
                last_exit_idx = int(valid_exit.index[-1])
                last_exit_dir = "long" if last_exit_val == 1 else "short"

                if last_exit_idx > entry_idx:
                    exit_warning = (last_exit_dir != entry_dir)
                    bars_since_exit = last_idx - last_exit_idx

        high_since_signal = None
        low_since_signal = None
        high_since_kline_count = None
        low_since_kline_count = None
        max_drawdown = None
        key_alpha_values = None
        trailing_stop_price = None

        if entry_idx and entry_price is not None:
            high_idx = int(df[_HIGH].iloc[entry_idx:].idxmax())
            low_idx = int(df[_LOW].iloc[entry_idx:].idxmin())
            high_since_kline_count = high_idx - entry_idx
            low_since_kline_count = low_idx - entry_idx
            high_since_signal = float(df.iloc[high_idx][_HIGH])
            low_since_signal = float(df.iloc[low_idx][_LOW])

            alpha_trend_values = df[_ALPHA_TREND].values
            stop_loss_reference_price = _find_recent_consecutive_alpha_trend(alpha_trend_values, entry_idx)

            trailing_stop_price = float(last_row[_ALPHA_TREND])
            if entry_dir == "long":
                max_drawdown = (high_since_signal - close) / high_since_signal if high_since_signal else None
                if trailing_stop_price <= entry_price:
                    trailing_stop_price = stop_loss_reference_price
            elif entry_dir == "short":
                max_drawdown = (close - low_since_signal) / low_since_signal if low_since_signal else None
                if trailing_stop_price >= entry_price:
                    trailing_stop_price = stop_loss_reference_price

            alpha_values = df[_ALPHA_TREND].iloc[entry_idx:].values
            _n = 2 if len(alpha_values) > 10 else 1
            value_counts_series = pd.Series(alpha_values).value_counts()
            frequent_values = value_counts_series[value_counts_series >= _n].index.tolist()
            key_alpha_values = sorted([float(v) for v in frequent_values], reverse=entry_dir == "short")

            if trailing_stop_price:
                trailing_stop_price = truncate_decimal(trailing_stop_price, price_places)
        
        if entry_dir == "long" and at_mode == "rising" and price_above_at:
            overall = "bullish"
        elif entry_dir == "short" and at_mode == "falling" and not price_above_at:
            overall = "bearish"
        elif at_mode == "flat":
            overall = "neutral"
        else:
            overall = "weak"

        return AlphaTrendOutput(
            name=self.name,
            display_name=self.display_name,
            at_value=truncate_decimal(at_val, price_places),
            at_mode=at_mode,
            at_change_pct=at_change_pct,
            price_above_at=price_above_at,
            deviation_pct=deviation_pct,
            entry_direction=entry_dir,
            bars_since_entry=bars_since_entry,
            entry_price=entry_price,
            entry_deviation_pct=entry_deviation_pct,
            exit_warning=exit_warning,
            bars_since_exit=bars_since_exit,
            exit_tests=exit_tests,
            overall=overall,
            high_since_signal=high_since_signal,
            low_since_signal=low_since_signal,
            high_since_kline_count=high_since_kline_count,
            low_since_kline_count=low_since_kline_count,
            max_drawdown=max_drawdown,
            key_alpha_values=key_alpha_values,
            stop_loss_price=trailing_stop_price,
            take_profit_price=trailing_stop_price,
        )
    
    def get_column_names(self) -> list[str]:
        return [_ATR, _ATR_BASE_LOW, _ATR_BASE_HIGH, _MFI, _ALPHA_TREND, 
                _TREND_SHIFT2_CROSS, _TREND_CLOSE_CROSS]

    def calculate_trend_segments_stats(self, df: DataFrame) -> list[dict[str, float]]:
        """
        Calculate max and min high/low prices for each trend segment.
        Trend segments are defined as periods between buy/sell signals.

        Returns:
            List of dicts with segment statistics
        """
        df = df.reset_index(drop=True, inplace=False)
        
        if len(df) < self.period or _TREND_SHIFT2_CROSS not in df.columns:
            return []

        high_values = df[_HIGH].values.astype(np.float64)
        low_values = df[_LOW].values.astype(np.float64)
        alpha_trend = df[_ALPHA_TREND].values
        signal_values = df[_TREND_SHIFT2_CROSS].values

        segments: list[dict[str, float]] = []

        high_price = float('-inf')
        low_price = float('inf')
        weight = 0
        
        close = df[_CLOSE].values
        price_places = get_decimal_places((close[-1] + high_values[-1]) / 2)
        
        for i in range(len(alpha_trend)):
            if pd.notna(alpha_trend[i]):
                if i >= 2 and alpha_trend[i] == alpha_trend[i-1] == alpha_trend[i-2]:
                    high_price = max(high_price, high_values[i], high_values[i-1], high_values[i-2])
                    low_price = min(low_price, low_values[i], low_values[i-1], low_values[i-2])
                    weight += 1
                else:
                    if weight > 0:
                        segments.append({
                            'high_price': truncate_decimal(high_price, price_places),
                            'low_price': truncate_decimal(low_price, price_places),
                            'weight': weight,
                            'alpha_trend': truncate_decimal(float(alpha_trend[i-1]), price_places)
                        })
                        weight = 0
                        high_price = float('-inf')
                        low_price = float('inf')

        current_signal = None
        for i in range(len(signal_values)):
            signal_item = signal_values[i]
            if current_signal is None:
                if signal_item == 1 or signal_item == -1:
                    current_signal = signal_item
                    high_price = high_values[i]
                    low_price = low_values[i]
                    weight = 1
            else:
                high_price = max(high_price, high_values[i])
                low_price = min(low_price, low_values[i])
                weight += 1
                if pd.notna(signal_item) and signal_item != current_signal:
                    segments.append({
                        'high_price': truncate_decimal(high_price, price_places),
                        'low_price': truncate_decimal(low_price, price_places),
                        'weight': weight - 2,
                        'alpha_trend': truncate_decimal(float(alpha_trend[i-1]), price_places)
                    })
                    current_signal = signal_item
                    high_price = high_values[i]
                    low_price = low_values[i]
                    weight = 0

        return segments
