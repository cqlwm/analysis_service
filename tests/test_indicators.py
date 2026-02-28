"""指标模块测试"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
from dataclasses import dataclass


@pytest.fixture
def sample_ohlcv_data() -> pd.DataFrame:
    """获取真实OHLCV数据"""
    import ccxt
    
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'},
    })
    exchange.load_markets()
    
    ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=200)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    return df


class TestIndicatorRegistry:
    """测试指标注册中心"""
    
    def test_register_and_get(self):
        """测试指标注册和获取"""
        from indicators import IndicatorRegistry, BaseIndicator
        from indicators.base import IndicatorSignal

        @dataclass
        class DummyOutput:
            name: str
            display_name: str
            signal: IndicatorSignal
        
        class DummyIndicator(BaseIndicator):
            name = "dummy"
            display_name = "Dummy"
            
            def calculate(self, df):
                return df
            
            def summarize(self, df):
                return DummyOutput(
                    name=self.name,
                    display_name=self.display_name,
                    signal={"direction": None, "strength": None, "description": ""},
                )
        
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
        
        assert summary.name == 'rsi'
        assert summary.rsi is not None
        assert summary.signal is not None


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
        
        assert summary.name == 'macd'
        assert getattr(summary, 'macd', None) is not None


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
        assert 'ma20' in df.columns
        assert 'alpha_trend' in df.columns
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
        assert 'score_matrix' in summary
        assert 'total_score' in summary
        assert 'decision' in summary
        assert len(summary['indicators']) > 0

        matrix = summary['score_matrix']
        assert 'trend' in matrix
        assert 'structure' in matrix
        assert 'momentum' in matrix
        assert 'flow' in matrix
        assert 'volatility' in matrix
    
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
        print(prompt)
        
        assert "BTC/USDT" in prompt
        assert "1h" in prompt
        assert "MACD" in prompt
        assert "五层评分矩阵" in prompt
        assert "趋势层" in prompt
    
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
        
        assert summary.name == 'alpha_trend'
        assert summary.at_value is not None


class TestVolumeAndBollingerEnhancements:
    """测试文档化增强字段"""

    def test_volume_includes_obv(self, sample_ohlcv_data):
        from indicators.volume import VolumeIndicator

        indicator = VolumeIndicator()
        df = indicator.calculate(sample_ohlcv_data)
        summary = indicator.summarize(df)

        assert 'obv' in df.columns
        assert summary.obv is not None
        assert summary.obv_trend in {'inflow', 'outflow', 'flat'}

    def test_bollinger_includes_bandwidth(self, sample_ohlcv_data):
        from indicators.bollinger import BollingerBandsIndicator

        indicator = BollingerBandsIndicator()
        df = indicator.calculate(sample_ohlcv_data)
        summary = indicator.summarize(df)

        assert summary.bandwidth_pct >= 0
        assert summary.squeeze_state in {'compressed', 'normal', 'expanded'}
