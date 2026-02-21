"""指标注册中心 - 管理所有可用指标"""
from indicators.base import BaseIndicator
from typing import Type


class IndicatorRegistry:
    """指标注册中心，支持插件式指标扩展"""
    
    _indicators: dict[str, BaseIndicator] = {}
    _initialized: bool = False
    
    @classmethod
    def register(cls, indicator_instance: BaseIndicator) -> None:
        """注册指标实例"""
        cls._indicators[indicator_instance.name] = indicator_instance
    
    @classmethod
    def get(cls, name: str) -> BaseIndicator | None:
        """获取指定指标"""
        return cls._indicators.get(name)
    
    @classmethod
    def all(cls) -> list[BaseIndicator]:
        """获取所有已注册指标"""
        return list(cls._indicators.values())
    
    @classmethod
    def names(cls) -> list[str]:
        """获取所有指标名称"""
        return list(cls._indicators.keys())
    
    @classmethod
    def initialize(cls) -> None:
        """初始化并注册所有内置指标"""
        if cls._initialized:
            return
        
        # 延迟导入，避免循环依赖
        from indicators.rsi import RSIIndicator
        from indicators.macd import MACDIndicator
        from indicators.bollinger import BollingerBandsIndicator
        from indicators.volume import VolumeIndicator
        from indicators.moving_average import MAIndicator
        from indicators.atr import ATRIndicator
        from indicators.mfi import MFIIndicator
        
        # 自动注册
        for indicator_cls in [RSIIndicator, MACDIndicator, BollingerBandsIndicator,
                              VolumeIndicator, MAIndicator, ATRIndicator, MFIIndicator]:
            cls.register(indicator_cls())
        
        cls._initialized = True
    
    @classmethod
    def reset(cls) -> None:
        """重置注册表（主要用于测试）"""
        cls._indicators = {}
        cls._initialized = False
