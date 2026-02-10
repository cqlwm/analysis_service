"""
测试 main.py 的高波动率交易对分析功能
"""

from binance_ticker_monitor import BinanceTickerMonitor
import time

def test_monitor():
    """测试监控器是否能正常工作"""
    print("测试 BinanceTickerMonitor...")
    
    monitor = BinanceTickerMonitor(volatility_threshold=3.0)
    monitor.start()
    
    print("等待连接...")
    time.sleep(3)
    
    print(f"已收集 {monitor.stats['total_symbols']} 个交易对")
    
    if monitor.stats['total_symbols'] > 0:
        print("✓ 监控器工作正常")
        # 测试获取高波动率交易对
        high_vol = monitor.get_high_volatility_symbols()
        print(f"✓ 发现 {len(high_vol)} 个高波动率交易对")
    else:
        print("✗ 未能获取交易对数据")
    
    monitor.stop()
    print("\n测试完成！")


def test_symbol_format():
    """测试交易对格式转换"""
    test_cases = [
        ("BTCUSDT", "BTC/USDT"),
        ("ETHUSDT", "ETH/USDT"),
        ("SOLUSDT", "SOL/USDT"),
    ]
    
    print("\n测试交易对格式转换:")
    for symbol_ws, expected in test_cases:
        symbol_ccxt = f"{symbol_ws[:-4]}/USDT"
        status = "✓" if symbol_ccxt == expected else "✗"
        print(f"  {status} {symbol_ws} -> {symbol_ccxt}")


if __name__ == "__main__":
    test_symbol_format()
    test_monitor()
