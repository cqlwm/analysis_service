"""指标模块 - 插件化技术指标系统"""
from indicators.base import BaseIndicator, IndicatorSummaryOutput, SignalDirection, IndicatorSignal
from indicators.registry import IndicatorRegistry

from indicators.alpha_trend import AlphaTrendOutput
from indicators.rsi import RSIOutput
from indicators.macd import MACDOutput
from indicators.bollinger import BollingerOutput
from indicators.volume import VolumeOutput
from indicators.atr import ATROutput
from indicators.moving_average import MAOutput
from indicators.mfi import MFIOutput

__all__ = [
    'BaseIndicator',
    'IndicatorSummaryOutput',
    'SignalDirection',
    'IndicatorSignal',
    'IndicatorRegistry',
    'AlphaTrendOutput',
    'RSIOutput',
    'MACDOutput',
    'BollingerOutput',
    'VolumeOutput',
    'ATROutput',
    'MAOutput',
    'MFIOutput',
]

def _init_indicators():
    from indicators.rsi import RSIIndicator
    from indicators.macd import MACDIndicator
    from indicators.bollinger import BollingerBandsIndicator
    from indicators.volume import VolumeIndicator
    from indicators.moving_average import MAIndicator
    from indicators.atr import ATRIndicator
    from indicators.mfi import MFIIndicator
    from indicators.alpha_trend import AlphaTrendIndicator
    
    IndicatorRegistry.register(RSIIndicator())
    IndicatorRegistry.register(MACDIndicator())
    IndicatorRegistry.register(BollingerBandsIndicator())
    IndicatorRegistry.register(VolumeIndicator())
    IndicatorRegistry.register(MAIndicator())
    IndicatorRegistry.register(ATRIndicator())
    IndicatorRegistry.register(MFIIndicator())
    IndicatorRegistry.register(AlphaTrendIndicator())


_init_indicators()
