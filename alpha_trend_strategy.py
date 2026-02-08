import numpy as np
import pandas as pd
from pandas import DataFrame
from typing import Any, Dict, Literal, TypedDict
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

class IndicatorSummary(TypedDict):
    df: DataFrame
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
        
        def _find_recent_consecutive_alpha_trend(alpha_trend_values: np.ndarray, current_index: int):
            for i in range(current_index - 2, -1, -1):
                if not np.isnan(alpha_trend_values[i]) and alpha_trend_values[i] == alpha_trend_values[i+1] == alpha_trend_values[i+2]:
                    return alpha_trend_values[i]
            return np.nan
        
        stop_loss_reference_price = _find_recent_consecutive_alpha_trend(np.asarray(df[_alpha_trend].values), last_signal_idx)

        # Calculate max/min prices since signal
        high_index = int(df[_high].iloc[last_signal_idx:].idxmax())
        low_index = int(df[_low].iloc[last_signal_idx:].idxmin())
        high_kline_n = high_index - last_signal_idx + 1
        low_kline_n = low_index - last_signal_idx + 1
        high_since_signal = float(df.iloc[high_index][_high])
        low_since_signal = float(df.iloc[low_index][_low])

        entry_price = float(df.iloc[last_signal_idx][_close])
        entry_alpha_trend = float(df.iloc[last_signal_idx][_alpha_trend])

        alpha_trend_value = float(current_row[_alpha_trend])
        trailing_stop_price = alpha_trend_value
        
        last_signal = int(df.iloc[last_signal_idx][_trend_shift2_cross_signal])
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

        info = NewSignalInfo(
            position_side='long' if last_signal == 1 else 'short',
            order_side='buy' if last_signal == 1 else 'sell',
            entry_price=entry_price,
            stop_loss_price=[stop_loss_reference_price],
            take_profit_price=[trailing_stop_price],
            entry_alpha_trend=entry_alpha_trend,
            high_since_signal=high_since_signal,
            low_since_signal=low_since_signal,
            high_since_kline_count=high_kline_n,
            low_since_kline_count=low_kline_n,
            latest_price=latest_price,
            key_alpha_values=key_alpha_values,
            max_drawdown=max_drawdown,
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

        high_values, low_values, signal_values = df[[_high, _low, _trend_shift2_cross_signal]].values.T.astype(np.float64)

        segments: list[dict[str, float]] = []

        current_signal = None
        high_price = float('-inf')
        low_price = float('inf')
        duration = 0
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
                duration += 1
                if pd.notna(signal_item) and signal_item != current_signal:
                    segments.append({
                        'high_price': high_price,
                        'low_price': low_price,
                        'duration': duration
                    })
                    current_signal = signal_item
                    high_price = high_values[i]
                    low_price = low_values[i]
                    duration = 0

        return segments

    def calculate_clustered_support_resistance(self, curr_price: float, segments: list[dict[str, float]]) -> dict[str, list[float]]:
        if not segments:
            return {'support': [], 'resistance': []}

        price_levels: list[float] = []
        for segment in segments:
            price_levels.extend([segment['high_price'], segment['low_price']])

        return {
            'support': list(set([p for p in price_levels if not np.isnan(p) and p <= curr_price])),
            'resistance': list(set([p for p in price_levels if not np.isnan(p) and p > curr_price])),
        }

    def calculate_indicators(self, df: DataFrame) -> DataFrame:
        """
        计算所有需要的技术指标
        """
        df = df.copy()
        df = self._alpha_trend_indicator(df)

        high, low, close, volume = df[['high', 'low', 'close', 'volume']].values.T.astype(np.float64)
        
        # 2. RSI 指标
        df['rsi'] = ta.RSI(close, timeperiod=self.rsi_period)
        
        # 3. MACD 指标
        macd, macd_signal, macd_hist = ta.MACD(
            close, 
            fastperiod=self.macd_fast,
            slowperiod=self.macd_slow, 
            signalperiod=self.macd_signal
        )
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        df['macd_hist'] = macd_hist
        
        # 4. 均线系统
        df['ma20'] = ta.SMA(close, timeperiod=20)
        df['ma50'] = ta.SMA(close, timeperiod=50)
        df['ma200'] = ta.SMA(close, timeperiod=200)
        
        # 5. 布林带
        upper, middle, lower = ta.BBANDS(close, timeperiod=20)
        df['bb_upper'] = upper
        df['bb_middle'] = middle
        df['bb_lower'] = lower
        
        # 6. 成交量指标
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
    
    def generate_signal(self, df: DataFrame, index: int = -1,total_capital: float = 10000) -> Dict[str, str | int | float | dict[str, float]]:
        """
        生成完整的交易信号
        
        返回:
        {
            'signal': 'BUY' | 'SELL' | 'HOLD',
            'direction': 1 | -1 | 0,
            'strength': 0-100,
            'entry_price': float,
            'stop_loss': float,
            'take_profit': float,
            'recommended_leverage': int,
            'risk_reward_ratio': float,
            'position_size': float,
            'analysis': str
        }
        """
        # 计算所有指标
        df = self.calculate_indicators(df)
        
        # 检测信号
        direction = self.detect_trend_reversal(df, index)
        
        if direction == 0:
            return {
                'signal': 'HOLD',
                'direction': 0,
                'strength': 0,
                'analysis': '当前无明确交易信号，建议观望'
            }
        
        # 计算信号强度
        strength = self.calculate_signal_strength(df, index, direction)
        
        # 信号强度过低，不建议交易
        if strength < 40:
            return {
                'signal': 'HOLD',
                'direction': 0,
                'strength': strength,
                'analysis': f'信号强度不足（{strength:.1f}%），建议等待更好的入场机会'
            }
        
        # 计算入场、止损、止盈
        levels = self.calculate_entry_exit_levels(df, index, direction)
        
        # 检查盈亏比是否合理
        entry = levels['entry_price']
        stop = levels['stop_loss']
        target = levels['take_profit']
        
        risk = abs(entry - stop)
        reward = abs(target - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        
        if rr_ratio < self.min_risk_reward_ratio:
            return {
                'signal': 'HOLD',
                'direction': 0,
                'strength': strength,
                'analysis': f'盈亏比不足（{rr_ratio:.2f}:1），最低要求{self.min_risk_reward_ratio}:1'
            }
        
        # 计算仓位和杠杆
        position_info = self.calculate_position_size_and_leverage(
            entry, stop, target, total_capital
        )
        
        # 生成分析报告
        current = df.iloc[index]
        signal_type = 'BUY' if direction == 1 else 'SELL'
        
        analysis = self._generate_analysis_text(current, direction, strength, levels, position_info)
        
        return {
            'signal': signal_type,
            'direction': direction,
            'strength': round(strength, 1),
            'entry_price': levels['entry_price'],
            'stop_loss': levels['stop_loss'],
            'take_profit': levels['take_profit'],
            'recommended_leverage': position_info['recommended_leverage'],
            'risk_reward_ratio': position_info['risk_reward_ratio'],
            'risk_percent': position_info['risk_percent'],
            'position_size': position_info['position_size'],
            'position_value': position_info['position_value'],
            'margin_required': position_info['margin_required'],
            'max_loss': position_info['max_loss'],
            'potential_profit': position_info['potential_profit'],
            'analysis': analysis,
            'indicators': {
                'close': round(current['close'], 2),
                'alpha_trend': round(current['alpha_trend'], 2),
                'rsi': round(current['rsi'], 2),
                'macd': round(current['macd'], 2),
                'macd_signal': round(current['macd_signal'], 2),
                'mfi': round(current['mfi'], 2),
                'atr': round(current['atr'], 2),
                'volume_ratio': round(current['volume_ratio'], 2)
            }
        }
    
    def _generate_analysis_text(self, current: pd.Series, direction: int, strength: float, levels:  Dict[str, float], position_info: Dict[str, float]) -> str:
        """
        生成分析文本
        """
        signal_name = "做多" if direction == 1 else "做空"
        
        analysis = f"""
【交易信号分析】

信号类型: {signal_name}
信号强度: {strength:.1f}% {'(强)' if strength >= 70 else '(中)' if strength >= 50 else '(弱)'}

【技术指标状态】
当前价格: {current['close']:.2f}
Alpha Trend: {current['alpha_trend']:.2f} ({('多头' if current['alpha_trend_direction'] == 1 else '空头')})
RSI: {current['rsi']:.2f} ({('超卖' if current['rsi'] < 30 else '超买' if current['rsi'] > 70 else '中性')})
MACD: {current['macd']:.2f} (信号线: {current['macd_signal']:.2f})
MFI: {current['mfi']:.2f}
成交量比率: {current['volume_ratio']:.2f}x

【交易计划】
入场价格: {levels['entry_price']:.2f}
止损价格: {levels['stop_loss']:.2f} (风险: {abs(levels['entry_price'] - levels['stop_loss']):.2f}, {position_info['risk_percent']:.2f}%)
止盈价格: {levels['take_profit']:.2f} (收益: {abs(levels['take_profit'] - levels['entry_price']):.2f})
盈亏比: {position_info['risk_reward_ratio']:.2f}:1

【仓位管理】
推荐杠杆: {position_info['recommended_leverage']}x
建议仓位: {position_info['position_size']:.4f} 单位
持仓价值: {position_info['position_value']:.2f}
所需保证金: {position_info['margin_required']:.2f}
最大亏损: {position_info['max_loss']:.2f}
潜在盈利: {position_info['potential_profit']:.2f}

【风险提示】
1. 严格执行止损，不要抱有侥幸心理
2. 分批建仓可以降低风险（建议分2-3次入场）
3. 盈利后及时移动止损到保本位
4. 关注重要支撑/阻力位的突破情况
"""
        return analysis.strip()
    
    # 指标摘要
    def generate_indicator_summary(self, df: DataFrame) -> IndicatorSummary:
        newSignalInfo = self._compute_last_signal_info(df)
        if newSignalInfo is None:
            raise ValueError("No valid signal info found in the DataFrame")
        
        # 支撑阻力位
        segments = self.calculate_trend_segments_stats(df)
        support_resistance = self.calculate_clustered_support_resistance(newSignalInfo['latest_price'], segments)
        return IndicatorSummary(
            df=df,
            info=newSignalInfo,
            segments=segments,
            support_resistance=support_resistance,
        )
        

def alpha_trend_strategy(df: DataFrame, **strategy_params: Any):
    """
    主策略函数：输入df，输出交易信号
    
    参数:
        df: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
        total_capital: 总资金量
        **strategy_params: 策略参数（可选）
        
    返回:
        {
            'signal': 'BUY' | 'SELL' | 'HOLD',
            'entry_price': float,
            'stop_loss': float,
            'take_profit': float,
            'recommended_leverage': int,
            'risk_reward_ratio': float,
            ...
        }
    """
    strategy = AlphaTrendStrategy(**strategy_params)
    df = strategy.calculate_indicators(df)
    summary = strategy.generate_indicator_summary(df)
    import json
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    



# 便捷函数：格式化输出
def print_trading_signal(signal: Dict[str, str | int | float | dict[str, float]]):
    """
    格式化打印交易信号
    """
    if signal['signal'] == 'HOLD':
        print("=" * 60)
        print(f"【持币观望】{signal['analysis']}")
        print("=" * 60)
        return
    
    print("=" * 60)
    print(f"【{signal['signal']} 信号】")
    print("=" * 60)
    print(f"\n入场方向: {'做多 (LONG)' if signal['direction'] == 1 else '做空 (SHORT)'}")
    print(f"信号强度: {signal['strength']}%")
    print(f"\n入场价格: {signal['entry_price']}")
    print(f"止损价格: {signal['stop_loss']}")
    print(f"止盈价格: {signal['take_profit']}")
    print(f"盈亏比: {signal['risk_reward_ratio']}:1")
    print(f"\n推荐杠杆: {signal['recommended_leverage']}x")
    print(f"建议仓位: {signal['position_size']} 单位")
    print(f"所需保证金: {signal['margin_required']}")
    print(f"潜在盈利: {signal['potential_profit']}")
    print(f"最大亏损: {signal['max_loss']}")
    print("\n" + "=" * 60)
    print(signal['analysis'])
    print("=" * 60)


if __name__ == "__main__":
    # 示例使用
    print("Alpha Trend 交易策略已加载")
    print("\n使用方法:")
    print("1. 准备数据: df with columns ['open', 'high', 'low', 'close', 'volume']")
    print("2. 调用策略: signal = alpha_trend_strategy(df, total_capital=10000)")
    print("3. 查看信号: print_trading_signal(signal)")
