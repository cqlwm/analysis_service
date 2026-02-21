"""指标模块测试"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def sample_ohlcv_data() -> pd.DataFrame:
    """生成模拟OHLCV数据"""
    np.random.seed(42)
    n = 100
    
    # 生成价格数据
    base_price = 100.0
    prices = [base_price]
    for _ in range(n - 1):
        change = np.random.randn() * 2
        prices.append(prices[-1] * (1 + change / 100))
    
    # 生成OHLCV数据
    data = {
        'timestamp': pd.date_range('2024-01-01', periods=n, freq='1h').astype(int) // 10**9,
        'datetime': pd.date_range('2024-01-01', periods=n, freq='1h'),
        'open': prices,
        'high': [p * (1 + abs(np.random.randn()) * 0.02) for p in prices],
        'low': [p * (1 - abs(np.random.randn()) * 0.02) for p in prices],
        'close': prices,
        'volume': [abs(np.random.randn() * 10000) for _ in range(n)],
    }
    
    return pd.DataFrame(data)


class TestIndicatorRegistry:
    """测试指标注册中心"""
    
    def test_register_and_get(self):
        """测试指标注册和获取"""
        from indicators import IndicatorRegistry, BaseIndicator
        
        class DummyIndicator(BaseIndicator):
            name = "dummy"
            display_name = "Dummy"
            
            def calculate(self, df):
                return df
            
            def summarize(self, df, latest_idx=-1):
                return {"name": self.name, "values": {}, "signal": None, "summary": ""}
        
        # 注册
        IndicatorRegistry.register(DummyIndicator())
        
        # 获取
        ind = IndicatorRegistry.get("dummy")
        assert ind is not None
        assert ind.name == "dummy"
        
        # 清理
        del IndicatorRegistry._indicators["dummy"]
    
    def test_all_indicators(self):
        """测试获取所有指标"""
        from indicators import IndicatorRegistry
        
        all_ind = IndicatorRegistry.all()
        assert len(all_ind) > 0
        
        names = [ind.name for ind in all_ind]
        assert "rsi" in names
        assert "macd" in names
        assert "bollinger" in names


class TestRSIIndicator:
    """测试RSI指标"""
    
    def test_calculate(self, sample_ohlcv_data):
        """测试RSI计算"""
        from indicators.rsi import RSIIndicator
        
        indicator = RSIIndicator()
        df = indicator.calculate(sample_ohlcv_data)
        
        assert 'rsi' in df.columns
        assert df['rsi'].notna().any()
    
    def test_summarize(self, sample_ohlcv_data):
        """测试RSI摘要"""
        from indicators.rsi import RSIIndicator
        
        indicator = RSIIndicator()
        df = indicator.calculate(sample_ohlcv_data)
        summary = indicator.summarize(df)
        
        assert summary['name'] == 'rsi'
        assert 'rsi' in summary['values']
        assert 'signal' in summary  # 验证signal字段存在


class TestMACDIndicator:
    """测试MACD指标"""
    
    def test_calculate(self, sample_ohlcv_data):
        """测试MACD计算"""
        from indicators.macd import MACDIndicator
        
        indicator = MACDIndicator()
        df = indicator.calculate(sample_ohlcv_data)
        
        assert 'macd' in df.columns
        assert 'macd_signal' in df.columns
        assert 'macd_hist' in df.columns
    
    def test_summarize(self, sample_ohlcv_data):
        """测试MACD摘要"""
        from indicators.macd import MACDIndicator
        
        indicator = MACDIndicator()
        df = indicator.calculate(sample_ohlcv_data)
        summary = indicator.summarize(df)
        
        assert summary['name'] == 'macd'
        assert 'macd' in summary['values']


class TestBollingerBandsIndicator:
    """测试布林带指标"""
    
    def test_calculate(self, sample_ohlcv_data):
        """测试布林带计算"""
        from indicators.bollinger import BollingerBandsIndicator
        
        indicator = BollingerBandsIndicator()
        df = indicator.calculate(sample_ohlcv_data)
        
        assert 'bb_upper' in df.columns
        assert 'bb_middle' in df.columns
        assert 'bb_lower' in df.columns


class TestCompositeStrategy:
    """测试复合策略"""
    
    def test_calculate_all(self, sample_ohlcv_data):
        """测试计算所有指标"""
        from strategies import CompositeStrategy
        
        strategy = CompositeStrategy()
        df = strategy.calculate_all(sample_ohlcv_data)
        
        # 检查必要的列存在
        assert 'rsi' in df.columns
        assert 'macd' in df.columns
        assert 'bb_upper' in df.columns
    
    def test_generate_summary(self, sample_ohlcv_data):
        """测试生成摘要"""
        from strategies import CompositeStrategy
        
        strategy = CompositeStrategy()
        df = strategy.calculate_all(sample_ohlcv_data)
        summary = strategy.generate_summary(df)
        
        assert 'indicators' in summary
        assert 'latest_price' in summary
        assert len(summary['indicators']) > 0
    
    def test_custom_indicators(self, sample_ohlcv_data):
        """测试指定指标"""
        from strategies import CompositeStrategy
        
        strategy = CompositeStrategy(indicator_names=['rsi', 'macd'])
        df = strategy.calculate_all(sample_ohlcv_data)
        
        assert 'rsi' in df.columns
        assert 'macd' in df.columns
        assert len(strategy.indicator_names) == 2


class TestPromptBuilder:
    """测试Prompt构建器"""
    
    def test_build_prompt(self, sample_ohlcv_data):
        """测试构建Prompt"""
        from prompts import PromptBuilder
        
        builder = PromptBuilder()
        prompt = builder.build_analysis_prompt(
            symbol="BTC/USDT",
            timeframe="1h",
            data_range="2024-01-01 ~ 2024-01-05",
            df=sample_ohlcv_data
        )
        
        assert "BTC/USDT" in prompt
        assert "1h" in prompt
        assert "RSI" in prompt or "MACD" in prompt
    
    def test_get_latest_values(self, sample_ohlcv_data):
        """测试获取最新值"""
        from prompts import PromptBuilder
        
        builder = PromptBuilder()
        values = builder.get_latest_values(sample_ohlcv_data)
        
        assert 'rsi' in values or 'macd' in values


class TestAlphaTrendIndicator:
    """测试Alpha Trend指标"""
    
    def test_calculate(self, sample_ohlcv_data):
        """测试Alpha Trend计算"""
        from indicators.alpha_trend import AlphaTrendIndicator
        
        indicator = AlphaTrendIndicator()
        df = indicator.calculate(sample_ohlcv_data)
        
        assert 'alpha_trend' in df.columns
        assert 'atr' in df.columns
        assert 'mfi' in df.columns
    
    def test_summarize(self, sample_ohlcv_data):
        """测试Alpha Trend摘要"""
        from indicators.alpha_trend import AlphaTrendIndicator
        
        indicator = AlphaTrendIndicator()
        df = indicator.calculate(sample_ohlcv_data)
        summary = indicator.summarize(df)
        
        assert summary['name'] == 'alpha_trend'
        assert 'alpha_trend' in summary['values']
