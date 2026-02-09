"""
改进版 Alpha Trend 策略
增强止盈点计算，支持多种方法
"""

import numpy as np
import pandas as pd
from pandas import DataFrame
from typing import Dict, List, Tuple, Optional
import talib as ta


class ImprovedAlphaTrendStrategy:
    """
    改进版Alpha Trend策略
    
    新增功能：
    1. 多种止盈计算方法（ATR/支撑阻力/斐波那契/混合）
    2. 动态止盈目标调整
    3. 分批止盈建议
    4. 移动止损计算
    """
    
    def __init__(
        self,
        atr_multiple: float = 1.0,
        period: int = 8,
        take_profit_method: str = "hybrid",  # "atr" / "support_resistance" / "fibonacci" / "hybrid"
        profit_ratio_t1: float = 1.5,  # 目标1的盈亏比
        profit_ratio_t2: float = 3.0,  # 目标2的盈亏比
        profit_ratio_t3: float = 4.5,  # 目标3的盈亏比
    ):
        self.atr_multiple = atr_multiple
        self.period = period
        self.take_profit_method = take_profit_method
        self.profit_ratio_t1 = profit_ratio_t1
        self.profit_ratio_t2 = profit_ratio_t2
        self.profit_ratio_t3 = profit_ratio_t3
    
    def calculate_indicators(self, df: DataFrame) -> DataFrame:
        """计算技术指标"""
        df = df.copy()
        
        high = df['high'].values.astype(np.float64)
        low = df['low'].values.astype(np.float64)
        close = df['close'].values.astype(np.float64)
        volume = df['volume'].values.astype(np.float64)
        
        # ATR
        atr = ta.ATR(high, low, close, timeperiod=self.period)
        atr_range = atr * self.atr_multiple
        atr_base_low = low - atr_range
        atr_base_high = high + atr_range
        
        # MFI
        mfi = ta.MFI(high, low, close, volume, timeperiod=self.period)
        
        df['atr'] = atr
        df['atr_base_low'] = atr_base_low
        df['atr_base_high'] = atr_base_high
        df['mfi'] = mfi
        
        # Alpha Trend
        alpha_trend = np.full(len(df), np.nan)
        if self.period < len(df):
            alpha_trend[self.period] = (
                atr_base_low[self.period] if mfi[self.period] >= 50 
                else atr_base_high[self.period]
            )
            
            for i in range(self.period + 1, len(df)):
                if mfi[i] >= 50:
                    alpha_trend[i] = max(alpha_trend[i-1], atr_base_low[i])
                else:
                    alpha_trend[i] = min(alpha_trend[i-1], atr_base_high[i])
        
        df['alpha_trend'] = alpha_trend
        
        # RSI
        df['rsi'] = ta.RSI(close, timeperiod=14)
        
        # MACD
        macd, signal, hist = ta.MACD(close)
        df['macd'] = macd
        df['macd_signal'] = signal
        
        return df
    
    def find_support_resistance_levels(self, df: DataFrame, lookback: int = 50) -> Tuple[List[float], List[float]]:
        """
        寻找支撑和阻力位
        
        返回: (support_levels, resistance_levels)
        """
        recent = df.tail(lookback)
        
        # 找峰值和谷值
        highs = np.array(recent['high'], dtype=np.float64)
        lows = np.array(recent['low'], dtype=np.float64)
        
        # 简单方法：找局部最高/最低点
        resistance: List[float] = []
        support: List[float] = []
        
        for i in range(2, len(recent) - 2):
            # 阻力位：当前高点高于前后高点
            if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and
                highs[i] > highs[i+1] and highs[i] > highs[i+2]):
                resistance.append(highs[i])
            
            # 支撑位：当前低点低于前后低点
            if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and
                lows[i] < lows[i+1] and lows[i] < lows[i+2]):
                support.append(lows[i])
        
        # 按价格排序
        resistance.sort(reverse=True)
        support.sort()
        
        return support, resistance
    
    def calculate_take_profit_atr(
        self,
        entry_price: float,
        stop_loss: float,
        atr: float,
        direction: int
    ) -> Tuple[float, float, float]:
        """基于ATR计算止盈"""
        risk = abs(entry_price - stop_loss)
        
        if direction == 1:  # 做多
            t1 = entry_price + (risk * self.profit_ratio_t1)
            t2 = entry_price + (risk * self.profit_ratio_t2)
            t3 = entry_price + (risk * self.profit_ratio_t3)
        else:  # 做空
            t1 = entry_price - (risk * self.profit_ratio_t1)
            t2 = entry_price - (risk * self.profit_ratio_t2)
            t3 = entry_price - (risk * self.profit_ratio_t3)
        
        return t1, t2, t3
    
    def calculate_take_profit_sr(
        self,
        entry_price: float,
        support_levels: List[float],
        resistance_levels: List[float],
        direction: int,
        atr: float  # 用于fallback
    ) -> Tuple[float, float, float]:
        """基于支撑阻力计算止盈"""
        
        if direction == 1:  # 做多，找阻力位
            # 筛选高于入场价的阻力位
            valid_resistance = [r for r in resistance_levels if r > entry_price]
            
            if len(valid_resistance) >= 3:
                # 从近到远取3个阻力位
                valid_resistance.sort()
                return (
                    valid_resistance[0],
                    valid_resistance[min(1, len(valid_resistance)-1)],
                    valid_resistance[min(2, len(valid_resistance)-1)]
                )
            else:
                # fallback到ATR方法
                return self.calculate_take_profit_atr(
                    entry_price,
                    entry_price - atr * 1.5,  # 假设止损
                    atr,
                    direction
                )
        
        else:  # 做空，找支撑位
            valid_support = [s for s in support_levels if s < entry_price]
            
            if len(valid_support) >= 3:
                valid_support.sort(reverse=True)
                return (
                    valid_support[0],
                    valid_support[min(1, len(valid_support)-1)],
                    valid_support[min(2, len(valid_support)-1)]
                )
            else:
                return self.calculate_take_profit_atr(
                    entry_price,
                    entry_price + atr * 1.5,
                    atr,
                    direction
                )
    
    def calculate_take_profit_fibonacci(
        self,
        df: DataFrame,
        entry_price: float,
        direction: int
    ) -> Tuple[float, float, float]:
        """基于斐波那契扩展计算止盈"""
        recent = df.tail(50)
        swing_low = recent['low'].min()
        swing_high = recent['high'].max()
        swing_range = swing_high - swing_low
        
        if direction == 1:  # 做多
            t1 = swing_low + swing_range * 1.272
            t2 = swing_low + swing_range * 1.618
            t3 = swing_low + swing_range * 2.618
        else:  # 做空
            t1 = swing_high - swing_range * 1.272
            t2 = swing_high - swing_range * 1.618
            t3 = swing_high - swing_range * 2.618
        
        return t1, t2, t3
    
    def calculate_take_profit_hybrid(
        self,
        df: DataFrame,
        entry_price: float,
        stop_loss: float,
        direction: int
    ) -> Tuple[float, float, float]:
        """
        混合方法：综合ATR和支撑阻力
        """
        current = df.iloc[-1]
        atr = current['atr']
        
        # 方法1: ATR
        t_atr = self.calculate_take_profit_atr(
            entry_price, stop_loss, atr, direction
        )
        
        # 方法2: 支撑阻力
        support, resistance = self.find_support_resistance_levels(df)
        t_sr = self.calculate_take_profit_sr(
            entry_price, support, resistance, direction, atr
        )
        
        # 综合两种方法
        if direction == 1:  # 做多
            # 第一目标：取较保守的（较近的）
            t1 = min(t_atr[0], t_sr[0])
            
            # 第二目标：取平均
            t2 = (t_atr[1] + t_sr[1]) / 2
            
            # 第三目标：取较激进的（较远的）
            t3 = max(t_atr[2], t_sr[2])
        else:  # 做空
            t1 = max(t_atr[0], t_sr[0])
            t2 = (t_atr[1] + t_sr[1]) / 2
            t3 = min(t_atr[2], t_sr[2])
        
        return t1, t2, t3
    
    def calculate_take_profit(
        self,
        df: DataFrame,
        entry_price: float,
        stop_loss: float,
        direction: int
    ) -> Dict:
        """
        计算止盈目标（统一接口）
        
        返回:
        {
            'targets': [t1, t2, t3],
            'method': 'hybrid',
            'risk_reward_ratios': [1.5, 3.0, 4.5],
            'reasoning': '...'
        }
        """
        # 根据选择的方法计算
        if self.take_profit_method == "atr":
            current = df.iloc[-1]
            targets = self.calculate_take_profit_atr(
                entry_price, stop_loss, current['atr'], direction
            )
            reasoning = f"基于ATR({current['atr']:.2f})的倍数计算"
            
        elif self.take_profit_method == "support_resistance":
            current = df.iloc[-1]
            support, resistance = self.find_support_resistance_levels(df)
            targets = self.calculate_take_profit_sr(
                entry_price, support, resistance, direction, current['atr']
            )
            reasoning = "基于前期支撑阻力位"
            
        elif self.take_profit_method == "fibonacci":
            targets = self.calculate_take_profit_fibonacci(
                df, entry_price, direction
            )
            reasoning = "基于斐波那契扩展比例"
            
        else:  # hybrid
            targets = self.calculate_take_profit_hybrid(
                df, entry_price, stop_loss, direction
            )
            reasoning = "综合ATR和支撑阻力的平衡方案"
        
        # 计算盈亏比
        risk = abs(entry_price - stop_loss)
        rr_ratios = [abs(t - entry_price) / risk for t in targets]
        
        return {
            'targets': [round(t, 2) for t in targets],
            'method': self.take_profit_method,
            'risk_reward_ratios': [round(r, 2) for r in rr_ratios],
            'reasoning': reasoning
        }
    
    def generate_signal(self, df: DataFrame, index: int = -1) -> Dict:
        """
        生成交易信号（含止盈目标）
        """
        # 计算指标
        df = self.calculate_indicators(df)
        
        current = df.iloc[index]
        prev = df.iloc[index - 1]
        
        # 检测信号
        direction = 0
        
        # 做多信号
        if (current['close'] > current['alpha_trend'] and 
            prev['close'] <= prev['alpha_trend'] and
            current['rsi'] < 70):
            direction = 1
        
        # 做空信号
        elif (current['close'] < current['alpha_trend'] and 
              prev['close'] >= prev['alpha_trend'] and
              current['rsi'] > 30):
            direction = -1
        
        if direction == 0:
            return {
                'signal': 'HOLD',
                'direction': 0,
                'reason': '无明确信号'
            }
        
        # 计算入场和止损
        entry_price = current['close']
        
        if direction == 1:
            stop_loss = current['alpha_trend']
        else:
            stop_loss = current['alpha_trend']
        
        # 计算止盈目标
        tp_info = self.calculate_take_profit(
            df, entry_price, stop_loss, direction
        )
        
        # 组合信号
        signal = {
            'signal': 'BUY' if direction == 1 else 'SELL',
            'direction': direction,
            'entry_price': round(entry_price, 2),
            'stop_loss': round(stop_loss, 2),
            'targets': tp_info['targets'],
            'risk_reward_ratios': tp_info['risk_reward_ratios'],
            'take_profit_method': tp_info['method'],
            'reasoning': tp_info['reasoning'],
            'indicators': {
                'alpha_trend': round(current['alpha_trend'], 2),
                'rsi': round(current['rsi'], 2),
                'atr': round(current['atr'], 2),
                'mfi': round(current['mfi'], 2)
            }
        }
        
        return signal
    
    def calculate_position_sizing(
        self,
        signal: Dict,
        total_capital: float,
        risk_percent: float = 2.0
    ) -> Dict:
        """
        计算仓位大小（分批建议）
        """
        if signal['direction'] == 0:
            return {}
        
        entry = signal['entry_price']
        stop = signal['stop_loss']
        targets = signal['targets']
        
        risk_per_unit = abs(entry - stop)
        risk_amount = total_capital * (risk_percent / 100)
        total_position = risk_amount / risk_per_unit
        
        # 分批建议
        batches = [
            {
                'batch': 1,
                'entry_price': entry,
                'size': total_position * 0.30,  # 30%
                'take_profit_at': targets[0],
                'action': '首批入场，测试性仓位'
            },
            {
                'batch': 2,
                'entry_price': entry,
                'size': total_position * 0.40,  # 40%
                'take_profit_at': targets[1],
                'action': '主力仓位，核心获利点'
            },
            {
                'batch': 3,
                'entry_price': entry,
                'size': total_position * 0.30,  # 30%
                'take_profit_at': targets[2],
                'action': '追求最大利润，用移动止损保护'
            }
        ]
        
        return {
            'total_position': round(total_position, 4),
            'risk_amount': round(risk_amount, 2),
            'batches': batches
        }


def print_improved_signal(signal: Dict, position_info: Optional[Dict] = None):
    """格式化打印信号"""
    
    if signal['signal'] == 'HOLD':
        print("\n" + "="*80)
        print("当前无交易信号")
        print("="*80)
        return
    
    print("\n" + "="*80)
    print(f"【{signal['signal']} 信号】")
    print("="*80)
    
    print(f"\n📍 入场价格: {signal['entry_price']}")
    print(f"🛡️  止损价格: {signal['stop_loss']}")
    print(f"   风险: {abs(signal['entry_price'] - signal['stop_loss']):.2f}")
    
    print(f"\n🎯 止盈目标:")
    for i, (target, rr) in enumerate(zip(signal['targets'], signal['risk_reward_ratios']), 1):
        print(f"   目标{i}: {target:.2f} (盈亏比 {rr:.1f}:1)")
    
    print(f"\n📊 技术指标:")
    for key, value in signal['indicators'].items():
        print(f"   {key}: {value}")
    
    print(f"\n💡 止盈方法: {signal['take_profit_method']}")
    print(f"   {signal['reasoning']}")
    
    if position_info:
        print(f"\n💰 仓位管理:")
        print(f"   总仓位: {position_info['total_position']:.4f}")
        print(f"   最大风险: {position_info['risk_amount']:.2f}")
        
        print(f"\n   分批建议:")
        for batch in position_info['batches']:
            print(f"   批次{batch['batch']}: {batch['size']:.4f} → "
                  f"目标 {batch['take_profit_at']:.2f}")
            print(f"          {batch['action']}")
    
    print("="*80)


# 使用示例
if __name__ == "__main__":
    print("改进版Alpha Trend策略已加载")
    print("\n支持的止盈计算方法:")
    print("- atr: 基于ATR倍数")
    print("- support_resistance: 基于关键价格位")
    print("- fibonacci: 基于斐波那契扩展")
    print("- hybrid: 综合方法（推荐）⭐")
    
    print("\n使用示例:")
    print("""
from improved_alpha_trend import ImprovedAlphaTrendStrategy, print_improved_signal
import pandas as pd

df = pd.read_csv('your_data.csv')

# 使用混合方法（推荐）
strategy = ImprovedAlphaTrendStrategy(take_profit_method="hybrid")
signal = strategy.generate_signal(df)

# 计算仓位
position_info = strategy.calculate_position_sizing(signal, total_capital=10000)

# 打印
print_improved_signal(signal, position_info)
    """)
