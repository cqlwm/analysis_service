"""指标模块 - 插件化技术指标系统"""
from indicators.base import BaseIndicator, IndicatorOutput, SignalDirection
from indicators.registry import IndicatorRegistry

# 导出常用类
__all__ = [
    'BaseIndicator',
    'IndicatorOutput', 
    'SignalDirection',
    'IndicatorRegistry',
]

# 自动初始化所有指标（延迟导入避免循环依赖）
def _init_indicators():
    from indicators.rsi import RSIIndicator
    from indicators.macd import MACDIndicator
    from indicators.bollinger import BollingerBandsIndicator
    from indicators.volume import VolumeIndicator
    from indicators.moving_average import MAIndicator
    from indicators.atr import ATRIndicator
    from indicators.mfi import MFIIndicator
    from indicators.alpha_trend import AlphaTrendIndicator
    
    # 注册所有指标
    IndicatorRegistry.register(RSIIndicator())
    IndicatorRegistry.register(MACDIndicator())
    IndicatorRegistry.register(BollingerBandsIndicator())
    IndicatorRegistry.register(VolumeIndicator())
    IndicatorRegistry.register(MAIndicator())
    IndicatorRegistry.register(ATRIndicator())
    IndicatorRegistry.register(MFIIndicator())
    IndicatorRegistry.register(AlphaTrendIndicator())


# 按需初始化
_init_indicators()
