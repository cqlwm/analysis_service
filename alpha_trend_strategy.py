import numpy as np
import pandas as pd
from pandas import DataFrame
from typing import Dict, Literal, TypedDict
import talib as ta

_high = 'high'
_low = 'low'
_close = 'close'
_volume = 'volume'
_atr = 'atr'
_atr_base_low = 'atr_base_low'
_atr_base_high = 'atr_base_high'
_mfi = 'mfi'
_alpha_trend = 'alpha_trend'
_trend_shift2_cross_signal = 'alpha_trend_shift2_cross_signal'
_trend_close_cross_signal = 'alpha_trend_close_cross_signal'
_rsi = 'rsi'
_macd = 'macd'
_macd_signal = 'macd_signal'
_macd_hist = 'macd_hist'
_ma20 = 'ma20'
_ma50 = 'ma50'
_ma200 = 'ma200'
_bb_upper = 'bb_upper'
_bb_middle = 'bb_middle'
_bb_lower = 'bb_lower'
_volume_ma = 'volume_ma'
_volume_ratio = 'volume_ratio'

class NewSignalInfo(TypedDict):
    position_side: Literal['long', 'short']
    order_side: Literal['buy', 'sell']
    entry_price: float
    stop_loss_price: list[float]
    take_profit_price: list[float]
    entry_alpha_trend: float
    high_since_signal: float    
    low_since_signal: float
    high_since_kline_count: int
    low_since_kline_count: int
    latest_price: float
    key_alpha_values: list[float]
    max_drawdown: float
    kline_count_since_signal: int
    latest_indicator_values: dict[str, float]

class IndicatorSummary(TypedDict):
    # df: DataFrame
    info: NewSignalInfo
    segments: list[dict[str, float]]
    support_resistance: dict[str, list[float]]
    


class AlphaTrendStrategy:
    """
    基于Alpha Trend指标的完善交易策略
    
    策略逻辑：
    1. 使用Alpha Trend作为主趋势指标
    2. 结合RSI、MACD、成交量等多维度确认
    3. 动态计算入场、止盈、止损价格
    4. 根据盈亏比推荐合理杠杆
    """
    
    def __init__(
        self,
        atr_multiple: float = 1.0,
        period: int = 8,
        rsi_period: int = 14,
        rsi_overbought: float = 70,
        rsi_oversold: float = 30,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        volume_ma_period: int = 20,
        min_risk_reward_ratio: float = 2.0,  # 最小盈亏比
        max_leverage: int = 10,  # 最大杠杆
        capital_risk_percent: float = 2.0,  # 每次交易风险占总资金的百分比
    ):
        self.atr_multiple = atr_multiple
        self.period = period
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.volume_ma_period = volume_ma_period
        self.min_risk_reward_ratio = min_risk_reward_ratio
        self.max_leverage = max_leverage
        self.capital_risk_percent = capital_risk_percent


    def _alpha_trend_indicator(self, df: DataFrame):
        atr_multiple = self.atr_multiple
        period = self.period

        # 计算技术指标
        high_values, low_values, close_values, volume_values = df[[_high, _low, _close, _volume]].values.T.astype(np.float64)
        atr_values = ta.ATR(high_values, low_values, close_values, timeperiod=period)
        atr_range_values = atr_values * atr_multiple
        atr_base_low_values = low_values - atr_range_values
        atr_base_high_values = high_values + atr_range_values
        mfi_values = ta.MFI(high_values, low_values, close_values, volume_values, timeperiod=period)

        df[_atr] = atr_values
        df[_atr_base_low] = atr_base_low_values
        df[_atr_base_high] = atr_base_high_values
        df[_mfi] = mfi_values

        alpha_trend_values = np.full(len(df), np.nan)
        if period < len(df):
            alpha_trend_values[period] = atr_base_low_values[period] if mfi_values[period] >= 50 else atr_base_high_values[period]
            
            for i in range(period + 1, len(df)):
                if mfi_values[i] >= 50:
                    alpha_trend_values[i] = max(alpha_trend_values[i-1], atr_base_low_values[i])
                else:
                    alpha_trend_values[i] = min(alpha_trend_values[i-1], atr_base_high_values[i])
        
        df[_alpha_trend] = alpha_trend_values

        alpha_trend_shift2 = df[_alpha_trend].shift(2)
        df[_trend_shift2_cross_signal] = np.select(
            [
                (df[_alpha_trend] > alpha_trend_shift2).astype(bool), 
                (df[_alpha_trend] < alpha_trend_shift2).astype(bool)
            ],
            [1, -1],                              
            default=np.nan
        )

        close_shift = df[_close].shift(1)
        alpha_trend_shift = df[_alpha_trend].shift(1)
        df[_trend_close_cross_signal] = np.select(
            [
                (df[_close] > df[_alpha_trend]) & (close_shift <= alpha_trend_shift), 
                (df[_close] < df[_alpha_trend]) & (close_shift >= alpha_trend_shift)
            ],
            [1, -1],
            default=np.nan
        )

        df.reset_index(inplace=True)
        current_signal = None
        for i in range(len(df)):
            sig = df.at[i, _trend_shift2_cross_signal]
            if pd.notna(sig):
                if sig == current_signal:
                    df.at[i, _trend_shift2_cross_signal] = np.nan
                else:
                    current_signal = sig
            trend_close_cross_signal = df.at[i, _trend_close_cross_signal]
            if pd.notna(trend_close_cross_signal):
                if trend_close_cross_signal == current_signal:
                    df.at[i, _trend_close_cross_signal] = np.nan

        return df


    def _compute_last_signal_info(self, df: DataFrame) -> NewSignalInfo | None:
        """Compute last signal information: type, price, kline count"""
        signal_series = df[_trend_shift2_cross_signal]
        if len(signal_series.dropna()) == 0:
            return None
        
        current_row = df.iloc[-1]
        latest_price = float(current_row[_close])
        last_signal_idx = int(signal_series.last_valid_index())  # type: ignore
        kline_count_since_signal = len(df) - last_signal_idx
        
        def _find_recent_consecutive_alpha_trend(alpha_trend_values: np.ndarray, current_index: int):
            for i in range(current_index - 2, -1, -1):
                if not np.isnan(alpha_trend_values[i]) and alpha_trend_values[i] == alpha_trend_values[i+1] == alpha_trend_values[i+2]:
                    return alpha_trend_values[i]
            return np.nan
        
        stop_loss_reference_price = _find_recent_consecutive_alpha_trend(np.asarray(df[_alpha_trend].values), last_signal_idx)

        high_index = int(df[_high].iloc[last_signal_idx:].idxmax())
        low_index = int(df[_low].iloc[last_signal_idx:].idxmin())
        high_kline_n = high_index - last_signal_idx
        low_kline_n = low_index - last_signal_idx
        high_since_signal = float(df.iloc[high_index][_high])
        low_since_signal = float(df.iloc[low_index][_low])

        entry_price = float(df.iloc[last_signal_idx][_close])
        entry_alpha_trend = float(df.iloc[last_signal_idx][_alpha_trend])

        last_signal = int(df.iloc[last_signal_idx][_trend_shift2_cross_signal])

        trailing_stop_price = float(current_row[_alpha_trend])
        if last_signal == 1:
            max_drawdown = (high_since_signal - latest_price) / high_since_signal
            if trailing_stop_price <= entry_price:
                trailing_stop_price = stop_loss_reference_price
        else:
            max_drawdown = (latest_price - low_since_signal) / low_since_signal
            if trailing_stop_price >= entry_price:
                trailing_stop_price = stop_loss_reference_price

        alpha_values = df[_alpha_trend].iloc[last_signal_idx:].values
        _n = 2 if len(alpha_values) > 10 else 1
        value_counts_series = pd.Series(alpha_values).value_counts()
        frequent_values = value_counts_series[value_counts_series >= _n].index.tolist()
        key_alpha_values = sorted(frequent_values, reverse=last_signal == -1)

        nf = len(str((entry_price+latest_price)/2).split('.')[1])

        info = NewSignalInfo(
            position_side='long' if last_signal == 1 else 'short',
            order_side='buy' if last_signal == 1 else 'sell',
            entry_price=entry_price,
            stop_loss_price=[trailing_stop_price],
            take_profit_price=[trailing_stop_price],
            entry_alpha_trend=entry_alpha_trend,
            high_since_signal=high_since_signal,
            low_since_signal=low_since_signal,
            high_since_kline_count=high_kline_n,
            low_since_kline_count=low_kline_n,
            latest_price=latest_price,
            key_alpha_values=key_alpha_values,
            max_drawdown=max_drawdown,
            kline_count_since_signal=kline_count_since_signal,
            latest_indicator_values={
                'atr': float(f'{current_row[_atr]:.{nf}f}'),
                'mfi': float(f'{current_row[_mfi]:.{nf}f}'),
                'rsi': float(f'{current_row[_rsi]:.{nf}f}'),
                'macd': float(f'{current_row[_macd]:.{nf}f}'),
                'macd_signal': float(f'{current_row[_macd_signal]:.{nf}f}'),
                'macd_hist': float(f'{current_row[_macd_hist]:.{nf}f}'),
                'ma20': float(f'{current_row[_ma20]:.{nf}f}'),
                'ma50': float(f'{current_row[_ma50]:.{nf}f}'),
                'ma200': float(f'{current_row[_ma200]:.{nf}f}'),
                'bb_upper': float(f'{current_row[_bb_upper]:.{nf}f}'),
                'bb_middle': float(f'{current_row[_bb_middle]:.{nf}f}'),
                'bb_lower': float(f'{current_row[_bb_lower]:.{nf}f}'),
                'volume': float(f'{current_row[_volume]:.{nf}f}'),
                'volume_ma': float(f'{current_row[_volume_ma]:.{nf}f}'),
                'volume_ratio': float(f'{current_row[_volume_ratio]:.{nf}f}'),
            }
        )
        return info

    def calculate_trend_segments_stats(self, df: DataFrame) -> list[dict[str, float]]:
        """
        Calculate max and min high/low prices for each trend segment.
        Trend segments are defined as periods between buy/sell signals.

        Returns:
            List of dicts with segment statistics
        """
        if len(df) < self.period or _trend_shift2_cross_signal not in df.columns:
            return []

        high_values, low_values, alpha_trend, signal_values = df[[_high, _low, _alpha_trend, _trend_shift2_cross_signal]].values.T.astype(np.float64)

        segments: list[dict[str, float]] = []

        high_price = float('-inf')
        low_price = float('inf')
        weight = 0
        nf = len(str((high_values[-1]+low_values[-1])/2).split('.')[1])
        
        for i in range(len(alpha_trend)):
            if pd.notna(alpha_trend[i]):
                if i >= 2 and alpha_trend[i] == alpha_trend[i-1] == alpha_trend[i-2]:
                    high_price = max(high_price, high_values[i], high_values[i-1], high_values[i-2])
                    low_price = min(low_price, low_values[i], low_values[i-1], low_values[i-2])
                    weight += 1
                                    
                else:
                    if weight > 0:
                        segments.append({
                            'high_price': high_price,
                            'low_price': low_price,
                            'weight': weight,
                            'alpha_trend': float(f'{alpha_trend[i-1]:.{nf}f}')
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
            else:
                high_price = max(high_price, high_values[i])
                low_price = min(low_price, low_values[i])
                weight += 1
                if pd.notna(signal_item) and signal_item != current_signal:
                    segments.append({
                        'high_price': high_price,
                        'low_price': low_price,
                        'weight': weight - 2,
                        'alpha_trend': float(f'{alpha_trend[i-1]:.{nf}f}')
                    })
                    current_signal = signal_item
                    high_price = high_values[i]
                    low_price = low_values[i]
                    weight = 0

        return segments

    def calculate_clustered_support_resistance(self, curr_price: float, segments: list[dict[str, float]]) -> dict[str, list[float]]:
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

    def calculate_indicators(self, df: DataFrame) -> DataFrame:
        """
        计算所有需要的技术指标
        """
        df = df.copy()
        df = self._alpha_trend_indicator(df)

        close, volume = df[['close', 'volume']].values.T.astype(np.float64)
        
        df['rsi'] = ta.RSI(close, timeperiod=self.rsi_period)
        
        macd, macd_signal, macd_hist = ta.MACD(close, fastperiod=self.macd_fast, slowperiod=self.macd_slow, signalperiod=self.macd_signal)
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        df['macd_hist'] = macd_hist
        
        df['ma20'] = ta.SMA(close, timeperiod=20)
        df['ma50'] = ta.SMA(close, timeperiod=50)
        df['ma200'] = ta.SMA(close, timeperiod=200)
        
        upper, middle, lower = ta.BBANDS(close, timeperiod=20)
        df['bb_upper'] = upper
        df['bb_middle'] = middle
        df['bb_lower'] = lower
        
        df['volume_ma'] = ta.SMA(volume, timeperiod=self.volume_ma_period)
        df['volume_ratio'] = volume / df['volume_ma']
                
        return df
    
    def detect_trend_reversal(self, df: DataFrame, index: int) -> int:
        """
        检测趋势反转信号
        返回: 1=多头反转, -1=空头反转, 0=无信号
        """
        if len(df) < 2:
            return 0
        if index < 0:
            index = len(df) + index
        if index < 2:
            return 0
            
        current = df.iloc[index]
        prev1 = df.iloc[index - 1]
        # prev2 = df.iloc[index - 2]
        
        # 多头反转条件
        long_conditions = [
            # 1. Alpha Trend 翻多
            current['alpha_trend_shift2_cross_signal'] == 1,
            # 2. 价格突破 Alpha Trend 线
            current['alpha_trend_direction'] == 1 and prev1['alpha_trend_direction'] <= 0,
            # 3. RSI 从超卖区反弹
            current['rsi'] > 30 and prev1['rsi'] <= 30,
            # 4. MACD 金叉或直方图转正
            (current['macd'] > current['macd_signal'] and prev1['macd'] <= prev1['macd_signal']) or
            (current['macd_hist'] > 0 and prev1['macd_hist'] <= 0),
        ]
        
        # 空头反转条件
        short_conditions = [
            # 1. Alpha Trend 翻空
            current['alpha_trend_shift2_cross_signal'] == -1,
            # 2. 价格跌破 Alpha Trend 线
            current['alpha_trend_direction'] == -1 and prev1['alpha_trend_direction'] >= 0,
            # 3. RSI 从超买区回落
            current['rsi'] < 70 and prev1['rsi'] >= 70,
            # 4. MACD 死叉或直方图转负
            (current['macd'] < current['macd_signal'] and prev1['macd'] >= prev1['macd_signal']) or
            (current['macd_hist'] < 0 and prev1['macd_hist'] >= 0),
        ]
        
        # 需要至少满足2个条件才产生信号
        long_score = sum(long_conditions)
        short_score = sum(short_conditions)
        
        if long_score >= 2:
            return 1
        elif short_score >= 2:
            return -1
        else:
            return 0
    
    def calculate_signal_strength(self, df: DataFrame, index: int, direction: int) -> float:
        """
        计算信号强度 (0-100)
        """
        current = df.iloc[index]
        score = 0
        max_score = 10
        
        if direction == 1:  # 多头信号
            # 1. RSI 位置 (10分)
            if current['rsi'] < 30:
                score += 2
            elif current['rsi'] < 50:
                score += 1
                
            # 2. MACD 强度 (10分)
            if current['macd_hist'] > 0:
                score += 1
            if current['macd'] > current['macd_signal']:
                score += 1
                
            # 3. 成交量确认 (20分)
            if current['volume_ratio'] > 1.5:
                score += 2
            elif current['volume_ratio'] > 1.0:
                score += 1
                
            # 4. 趋势一致性 (20分)
            if current['close'] > current['ma20']:
                score += 1
            if current['ma20'] > current['ma50']:
                score += 1
                
            # 5. 价格位置 (20分)
            if current['close'] < current['bb_lower']:
                score += 2
            elif current['close'] < current['bb_middle']:
                score += 1
                
            # 6. MFI 确认 (20分)
            if current['mfi'] >= 50:
                score += 2
                
        elif direction == -1:  # 空头信号
            # 1. RSI 位置
            if current['rsi'] > 70:
                score += 2
            elif current['rsi'] > 50:
                score += 1
                
            # 2. MACD 强度
            if current['macd_hist'] < 0:
                score += 1
            if current['macd'] < current['macd_signal']:
                score += 1
                
            # 3. 成交量确认
            if current['volume_ratio'] > 1.5:
                score += 2
            elif current['volume_ratio'] > 1.0:
                score += 1
                
            # 4. 趋势一致性
            if current['close'] < current['ma20']:
                score += 1
            if current['ma20'] < current['ma50']:
                score += 1
                
            # 5. 价格位置
            if current['close'] > current['bb_upper']:
                score += 2
            elif current['close'] > current['bb_middle']:
                score += 1
                
            # 6. MFI 确认
            if current['mfi'] < 50:
                score += 2
        
        return (score / max_score) * 100
    
    def calculate_entry_exit_levels(self, df: DataFrame, index: int, direction: int) -> Dict[str, float]:
        """
        计算入场价格、止损、止盈位
        """
        current = df.iloc[index]
        close = current['close']
        atr = current['atr']
        alpha_trend = current['alpha_trend']
        
        if direction == 1:  # 做多
            # 入场价格：当前收盘价或稍高
            entry_price = close
            
            # 止损：Alpha Trend 线下方或前低
            # 策略1: 使用 Alpha Trend 作为止损
            stop_loss_1 = alpha_trend
            
            # 策略2: 使用 ATR 计算止损（1.5倍ATR）
            stop_loss_2 = close - (1.5 * atr)
            
            # 策略3: 使用布林带下轨
            stop_loss_3 = current['bb_lower']
            
            # 取最近的止损位（更保守）
            stop_loss = max(stop_loss_1, stop_loss_2, stop_loss_3)
            
            # 止盈位
            # 目标1: 前阻力位
            take_profit_1 = current['resistance1']
            
            # 目标2: 基于ATR的动态止盈（3倍ATR）
            risk = entry_price - stop_loss
            take_profit_2 = entry_price + (3 * risk)  # 1:3 盈亏比
            
            # 目标3: 布林带上轨
            take_profit_3 = current['bb_upper']
            
            # 综合止盈位（取中间值）
            take_profit = np.median([take_profit_1, take_profit_2, take_profit_3])
            
        elif direction == -1:  # 做空
            # 入场价格
            entry_price = close
            
            # 止损：Alpha Trend 线上方或前高
            stop_loss_1 = alpha_trend
            stop_loss_2 = close + (1.5 * atr)
            stop_loss_3 = current['bb_upper']
            
            stop_loss = min(stop_loss_1, stop_loss_2, stop_loss_3)
            
            # 止盈位
            take_profit_1 = current['support1']
            risk = stop_loss - entry_price
            take_profit_2 = entry_price - (3 * risk)
            take_profit_3 = current['bb_lower']
            
            take_profit = np.median([take_profit_1, take_profit_2, take_profit_3])
        
        else:
            return {}
        
        return {
            'entry_price': round(entry_price, 2),
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'atr': round(atr, 2)
        }
    
    def calculate_position_size_and_leverage(self, entry_price: float, stop_loss: float, take_profit: float, total_capital: float = 10000) -> Dict[str, float]:
        """
        根据盈亏比计算推荐杠杆和仓位
        """
        # 计算风险和收益
        risk_per_unit = abs(entry_price - stop_loss)
        reward_per_unit = abs(take_profit - entry_price)
        
        # 盈亏比
        risk_reward_ratio = reward_per_unit / risk_per_unit if risk_per_unit > 0 else 0
        
        # 风险百分比
        risk_percent = (risk_per_unit / entry_price) * 100
        
        # 计算推荐杠杆
        # 基础逻辑：盈亏比越高，可以使用更高杠杆
        if risk_reward_ratio >= 3.0:
            base_leverage = min(5, self.max_leverage)
        elif risk_reward_ratio >= 2.0:
            base_leverage = min(3, self.max_leverage)
        elif risk_reward_ratio >= 1.5:
            base_leverage = min(2, self.max_leverage)
        else:
            base_leverage = 1  # 盈亏比不足，不建议使用杠杆
        
        # 根据风险百分比调整杠杆
        if risk_percent > 5:  # 单笔风险超过5%
            recommended_leverage = max(1, base_leverage - 2)
        elif risk_percent > 3:
            recommended_leverage = max(1, base_leverage - 1)
        else:
            recommended_leverage = base_leverage
        
        # 计算仓位大小（基于总资金的风险百分比）
        # 例如：愿意承担总资金2%的风险
        risk_amount = total_capital * (self.capital_risk_percent / 100)
        position_size = risk_amount / risk_per_unit
        position_value = position_size * entry_price
        
        # 使用杠杆后的实际保证金
        margin_required = position_value / recommended_leverage
        
        return {
            'risk_reward_ratio': round(risk_reward_ratio, 2),
            'risk_percent': round(risk_percent, 2),
            'recommended_leverage': int(recommended_leverage),
            'position_size': round(position_size, 4),
            'position_value': round(position_value, 2),
            'margin_required': round(margin_required, 2),
            'max_loss': round(risk_amount, 2),
            'potential_profit': round(reward_per_unit * position_size, 2)
        }
    

    def generate_indicator_summary(self, df: DataFrame) -> IndicatorSummary:
        newSignalInfo = self._compute_last_signal_info(df)
        if newSignalInfo is None:
            raise ValueError("No valid signal info found in the DataFrame")
        
        # 支撑阻力位
        segments = self.calculate_trend_segments_stats(df)
        support_resistance = self.calculate_clustered_support_resistance(newSignalInfo['latest_price'], segments)
        return IndicatorSummary(
            info=newSignalInfo,
            segments=segments,
            support_resistance=support_resistance,
        )
        
def generate_indicator_prompt(symbol: str, timeframe: str, data_range: str, summary: IndicatorSummary) -> str:
    """
    生成指标摘要的提示词
    
    注意：本信号基于 Alpha Trend 指标生成，信号发出时价格与当前价格可能存在偏差。
    请根据当前实际价格走势进行分析，灵活调整交易策略。
    """
    info = summary['info']
    segments = summary['segments']
    sr = summary['support_resistance']
    indicators = info['latest_indicator_values']
    
    # 取第一个支撑/阻力位
    key_support = sr['support'][0] if sr['support'] else 'N/A'
    key_resistance = sr['resistance'][0] if sr['resistance'] else 'N/A'
    
    # 从segments中提取支撑位和阻力位（带权重=停留时长）
    latest_price = info['latest_price']
    
    # 定义支撑/阻力位的类型
    class LevelWithWeight(TypedDict):
        level: float
        weight: int
        source: str
    
    # 收集支撑位：low_price <= 当前价格 的所有水平
    supports_with_weights: list[LevelWithWeight] = []
    for seg in segments:
        for level, level_type in [
            (seg['low_price'], '关键低点'),
            (seg['alpha_trend'], 'Alpha Trend')
        ]:
            if level <= latest_price:
                supports_with_weights.append({
                    'level': level,
                    'weight': int(seg['weight']),
                    'source': level_type
                })
    
    # 收集阻力位：high_price > 当前价格 的所有水平
    resistances_with_weights: list[LevelWithWeight] = []
    for seg in segments:
        for level, level_type in [
            (seg['high_price'], '关键高点'),
            (seg['alpha_trend'], 'Alpha Trend')
        ]:
            if level > latest_price:
                resistances_with_weights.append({
                    'level': level,
                    'weight': int(seg['weight']),
                    'source': level_type
                })
    
    # 按权重（停留时长）降序排序，然后取最近的5个
    supports_with_weights.sort(key=lambda x: (-x['weight'], -x['level']))
    resistances_with_weights.sort(key=lambda x: (-x['weight'], x['level']))
    
    # 取最近的5个
    top_supports = supports_with_weights[:5]
    top_resistances = resistances_with_weights[:5]
    
    # 生成支撑位表格
    support_table = "| 支撑位 | 停留时长(h) | 类型 |\n|--------|-------------|------|\n"
    for s in top_supports:
        support_table += f"| {s['level']:.6f} | {s['weight']} | {s['source']} |\n"
    
    # 生成阻力位表格
    resistance_table = "| 阻力位 | 停留时长(h) | 类型 |\n|--------|-------------|------|\n"
    for r in top_resistances:
        resistance_table += f"| {r['level']:.6f} | {r['weight']} | {r['source']} |\n"
    
    # 关键数据提取
    entry_price = info['entry_price']
    latest_price = info['latest_price']
    position = info['position_side']
    order_side = info['order_side']
    high_since_signal = info['high_since_signal']
    low_since_signal = info['low_since_signal']
    kline_count_since_signal = info['kline_count_since_signal']
    max_drawdown_pct = info['max_drawdown'] * 100
    
    # 计算偏离度
    price_deviation = (latest_price - entry_price) / entry_price * 100
    
    # 偏离状态判断
    if position == 'long':
        if latest_price > entry_price:
            deviation_status = f"价格高于入场价 {price_deviation:.2f}%，趋势延续"
        else:
            deviation_status = f"价格低于入场价 {abs(price_deviation):.2f}%，注意回调风险"
    else:
        if latest_price < entry_price:
            deviation_status = f"价格低于入场价 {abs(price_deviation):.2f}%，趋势延续"
        else:
            deviation_status = f"价格高于入场价 {price_deviation:.2f}%，注意反弹风险"
    
    # 当前趋势状态
    if position == 'long':
        trend_status = '多头趋势中' if latest_price > entry_price else '多头回调中'
    else:
        trend_status = '空头趋势中' if latest_price < entry_price else '空头反弹中'
    
    # 盈亏比计算
    stop_loss = info['stop_loss_price'][0]
    take_profit = info['take_profit_price'][0]
    
    # RSI 解读
    if indicators['rsi'] > 70:
        rsi_signal = '超买区域'
    elif indicators['rsi'] < 30:
        rsi_signal = '超卖区域'
    else:
        rsi_signal = '中性区域'
    
    # MACD 解读
    macd_cross = '金叉' if indicators['macd'] > indicators['macd_signal'] else '死叉'
    
    # MFI 解读
    mfi_signal = '资金流入' if indicators['mfi'] >= 50 else '资金流出'
    
    # Volume 解读
    volume_signal = '放量' if indicators['volume_ratio'] > 1 else '缩量'
    
    return f"""
📈 交易对: {symbol}
⏰ 时间周期: {timeframe}
📅 数据范围: {data_range}

# Alpha Trend 交易信号分析

## ⚠️ 重要提示 - 信号时效性说明
本信号基于 Alpha Trend 指标生成，**信号发出时价格与当前价格可能存在偏差**：
- **入场价格**: {entry_price}
- **当前价格**: {latest_price}
- **偏离度**: {deviation_status}

请根据当前实际价格走势进行分析，**不必拘泥于原始信号方向**，可灵活调整交易策略。
- 趋势偏好：优先考虑做空, 只有在多头趋势足够强势的情况下才考虑做多

---

## ⏱️ 信号时效性分析
| 项目 | 数值 | 解读 |
|------|------|------|
| 信号后经过K线数 | {kline_count_since_signal} | 若时间框架1h=1小时 |
| 入场价格 | {entry_price} | 原始入场点 |
| 当前价格 | {latest_price} | 最新价 |
| 价格偏离 | {price_deviation:+.2f}% | 相对入场价涨跌 |
| 信号后最高 | {high_since_signal} | ({high_since_signal}根K线内) |
| 信号后最低 | {low_since_signal} | ({low_since_signal}根K线内) |
| 最大回撤 | {max_drawdown_pct:.2f}% | 信号后最大回撤 |
| 趋势状态 | {trend_status} | 动态判断 |

## 📊 当前信号 vs 实际行情对比
| 项目 | 数值 |
|------|------|
| 原始持仓方向 | {position} ({'多' if position == 'long' else '空'}) |
| 原始交易方向 | {order_side} ({'买入' if order_side == 'buy' else '卖出'}) |

## 🎯 关键价位
- **当前价格**: {latest_price}
- **最近支撑**: {key_support}
- **最近阻力**: {key_resistance}
- **建议止损**: {stop_loss:.6f}
- **建议止盈**: {take_profit:.6f}

## 📈 技术指标
| 指标 | 数值 | 信号解读 |
|------|------|----------|
| RSI(14) | {indicators['rsi']:.2f} | {rsi_signal} |
| MFI | {indicators['mfi']:.2f} | {mfi_signal} |
| ATR | {indicators['atr']:.6f} | 波动率参考 |
| MACD | {indicators['macd']:.6f} | {macd_cross} |
| MA20 | {indicators['ma20']:.6f} | 短期均线 |
| MA50 | {indicators['ma50']:.6f} | 中期均线 |
| MA200 | {indicators['ma200']:.6f} | 长期均线 |
| BB Upper | {indicators['bb_upper']:.6f} | 布林上轨 |
| BB Middle | {indicators['bb_middle']:.6f} | 布林中轨 |
| BB Lower | {indicators['bb_lower']:.6f} | 布林下轨 |
| Volume Ratio | {indicators['volume_ratio']:.2f} | {volume_signal} |

## 🎯 多层级支撑与阻力（含停留时间权重）

### 📉 支撑位（按停留时长排序，越坚固的越靠前）
{support_table}
### 📈 阻力位（按停留时长排序，越坚固的越靠前）
{resistance_table}
### 💡 权重解读
- **停留时长(权重)** = 价格在该价位区间停留的小时数
- 权重越高，该价位越"坚固"，支撑/阻力越强
- **关键低点/高点** = 历史价格形成的明显转折点
- **Alpha Trend** = 动态指标线，也是重要的支撑/阻力参考

## 📝 任务要求
输出行情分析报告

1. **明确说明信号时效性**
2. **灵活给出交易建议**：
   - 如果当前价格仍支持原趋势方向 → 建议入场/加仓
   - 如果价格已大幅回调/反弹 → 建议反向操作或观望
3. **核心内容**：
   - 当前价格位置分析（在支撑/阻力位附近还是中间）
   - 入场理由（技术指标确认）
   - 止损止盈位（根据当前价格动态调整）
   - 风险提示（信号可能已过时）
4. markdown 格式输出

请生成完整的行情分析。
"""


# 快讯提示词
def generate_flash_prompt():
    return '''
基于上述指标信息和行情分析报告编写一则交易信号快讯。
注意：使用纯文本而非markdown格式。


示例1：

$ZIL dip 正在被买回，买家似乎在试图重新获得控制权。
立即做多 $ZIL 

入场：0.00455 – 0.00480

止损：0.00435

止盈1：0.00505

止盈2：0.00535

止盈3：0.00570

在回调后，卖压迅速减轻，价格回软后开始出现买盘。下行幅度在被捕获之前并未拉得太远，而反弹开始显现出更好的意图。整体感觉是买家在悄悄重新布局，这通常会为进一步上涨打开空间，只要需求保持活跃。

交易 $ZIL 在这里 👇


示例2:

$DUSK 反弹看起来正在失去力量，卖家开始退缩。
立即做空 $DUSK 

入场：0.114 – 0.119

止损：0.126

第一目标：0.107

第二目标：0.098

第三目标：0.089

上涨的推力没有保持，买家在反弹后看起来不舒服维护收益。力量不断被卖出，而下行反应开始变得更加顺畅。流动性感觉沉重，供应压向动量，这通常有利于继续下行，如果卖家保持活跃。

在这里交易 $DUSK  👇


示例3:

$YALA 强势上涨后稍作喘息，结构完好，回踩关键均线即机会。
立即做多 $YALA 

入场：0.00840 – 0.00860

止损：0.00822

目标1：0.00950

目标2：0.00995

在冲击关键阻力位后，价格进入高位盘整。买方趋势明确，短期均线形成动态支撑带。当前的缩量回调表明抛压有限，这通常是趋势延续中的健康停顿。只要价格在支撑区上方获得买盘承接，预计将再次向上测试并突破前高阻力。

交易 $YALA 机会在这里 👇

    '''

