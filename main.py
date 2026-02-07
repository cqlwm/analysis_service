import ccxt
import dotenv
import pandas as pd

dotenv.load_dotenv()

from llm_enhanced_strategy import llm_enhanced_strategy, print_enhanced_signal


def main():
    # 交易所配置
    symbol = 'ETH/USDT'
    timeframe = '1h'
    limit = 200  # 需要足够数据计算指标
    
    # 初始化Binance
    exchange = ccxt.binance({
        'enableRateLimit': True,
    })
    
    print(f"📊 正在获取 {symbol} {timeframe} K线数据...")
    
    # 获取K线数据
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    
    # 转换为DataFrame
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    print(f"✅ 获取到 {len(df)} 条K线数据")
    print(f"📅 数据范围: {df['timestamp'].iloc[0]} ~ {df['timestamp'].iloc[-1]}")
    
    # 调用LLM增强策略
    print("\n🤖 正在调用GPT进行市场分析...")
    result = llm_enhanced_strategy(df)
    
    # 打印结果
    print_enhanced_signal(result)


if __name__ == "__main__":
    main()
