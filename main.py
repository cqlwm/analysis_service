import ccxt
import dotenv
import pandas as pd
import openai
import os
from openai.types.chat.chat_completion_system_message_param import ChatCompletionSystemMessageParam
from openai.types.chat.chat_completion_user_message_param import ChatCompletionUserMessageParam
from openai.types.chat.chat_completion_assistant_message_param import ChatCompletionAssistantMessageParam
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from pandas import DataFrame
import time
import json
import threading

from alpha_trend_strategy import AlphaTrendStrategy, generate_flash_prompt, generate_indicator_prompt
from binance_ticker_monitor import BinanceTickerMonitor

dotenv.load_dotenv()


def fetch_ohlcv(symbol: str, timeframe: str = '1h') -> DataFrame:
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
        },
    })
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=350)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df


def generate_post(symbol: str, timeframe: str, df: DataFrame):
    strategy = AlphaTrendStrategy()
    df = strategy.calculate_indicators(df)
    summary = strategy.generate_indicator_summary(df)
    indicator_prompt = generate_indicator_prompt(
        symbol=symbol,
        timeframe=timeframe,
        data_range=f'{df["timestamp"].iloc[0]} ~ {df["timestamp"].iloc[-1]}',
        summary=summary
    )

    # 初始化OpenAI客户端
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE_URL")
    model_name = os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3.2")

    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    # 根据指标摘要生成分析报告
    messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(
            content="你是一个专业的加密货币交易分析员, 擅长分析技术指标和市场趋势, 并根据指标生成专业的交易分析报告。",
            role="system"),
        ChatCompletionUserMessageParam(content=indicator_prompt, role="user"),
    ]

    response1 = client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=2000,
        extra_body={
            'enable_thinking': True
        }
    )
    analysis_result = response1.choices[0].message.content or ""

    # 根据报告生成帖文
    messages.append(ChatCompletionAssistantMessageParam(content=analysis_result, role="assistant"))
    messages.append(ChatCompletionUserMessageParam(content=generate_flash_prompt(), role="user"))

    response2 = client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=200,
        extra_body={
            'enable_thinking': True
        }
    )
    final_post = response2.choices[0].message.content or ""

    return final_post


def save_post(symbol: str, post: str, extra_data: dict | None = None):
    """保存分析报告到文件
    
    Args:
        symbol: 交易对符号
        post: 生成的分析报告内容
        extra_data: 额外的数据（如波动率信息等）
    """
    symbol_clean = symbol.replace('/USDT', '')
    timestamp = int(time.time())
    data = {
        'symbols': [symbol_clean],
        'content': post,
        'timestamp': timestamp,
    }
    if extra_data:
        data.update(extra_data)
    
    with open(f'data/{symbol_clean}_{timestamp}.json', 'w') as f:
        f.write(json.dumps(data, indent=4, ensure_ascii=False))
    
    print(f"✓ 已保存: data/{symbol_clean}_{timestamp}.json")


def get_high_volatility_symbols(
    threshold: float = 3.0,
    monitor_duration: int = 60,
    max_symbols: int = 5
) -> list:
    """获取高波动率交易对
    
    Args:
        threshold: 波动率阈值（百分比）
        monitor_duration: 监控持续时间（秒）
        max_symbols: 返回的最大交易对数量
        
    Returns:
        高波动率交易对列表，每个元素包含symbol和波动率信息
    """
    print(f"\n{'='*60}")
    print(f"开始监控高波动率交易对...")
    print(f"阈值: {threshold}% | 监控时间: {monitor_duration}秒 | 最大数量: {max_symbols}")
    print(f"{'='*60}\n")
    

    
    # 等待连接建立
    print("等待WebSocket连接...")
    time.sleep(3)
    
    # 监控一段时间收集数据
    print(f"开始收集数据，持续 {monitor_duration} 秒...")
    for i in range(monitor_duration, 0, -1):
        if i % 10 == 0 or i <= 5:
            print(f"剩余时间: {i}秒 | 已收集 {monitor.stats['total_symbols']} 个交易对", end="\r")
        time.sleep(1)
    
    print("\n" + "="*60)
    
    # 获取高波动率交易对
    high_vol_symbols = monitor.get_high_volatility_symbols()
    monitor.stop()
    
    if not high_vol_symbols:
        print("未发现高波动率交易对")
        return []
    
    print(f"发现 {len(high_vol_symbols)} 个高波动率交易对")
    print(f"\n{'='*120}")
    print(f"{'排名':<6}{'交易对':<12}{'当前价格':<15}{'最大波动':<12}{'5分钟':<10}{'15分钟':<10}{'1小时':<10}{'4小时':<10}{'24小时':<10}")
    print(f"{'-'*120}")
    
    selected_symbols = high_vol_symbols[:max_symbols]
    
    for i, item in enumerate(selected_symbols, 1):
        changes = item['changes']
        print(
            f"{i:<6}"
            f"{item['symbol']:<12}"
            f"{item['current_price']:<15.8f}"
            f"{item['max_change']:<12.2f}%"
            f"{changes.get('5m') or 0:<10.2f}%"
            f"{changes.get('15m') or 0:<10.2f}%"
            f"{changes.get('1h') or 0:<10.2f}%"
            f"{changes.get('4h') or 0:<10.2f}%"
            f"{changes.get('24h') or 0:<10.2f}%"
        )
    
    print(f"{'='*120}\n")
    
    return selected_symbols


def analyze_high_volatility_symbols(
    threshold: float = 3.0,
    monitor_duration: int = 60,
    max_symbols: int = 5,
    timeframe: str = '1h'
):
    """分析高波动率交易对并生成报告
    
    Args:
        threshold: 波动率阈值（百分比）
        monitor_duration: 监控持续时间（秒）
        max_symbols: 分析的最大交易对数量
        timeframe: 分析的时间周期
    """
    # 获取高波动率交易对
    high_vol_symbols = get_high_volatility_symbols(
        threshold=threshold,
        monitor_duration=monitor_duration,
        max_symbols=max_symbols
    )
    
    if not high_vol_symbols:
        print("没有高波动率交易对需要分析")
        return
    
    print(f"\n开始生成分析报告...")
    print(f"时间周期: {timeframe}")
    print(f"{'='*60}\n")
    
    # 为每个高波动率交易对生成报告
    for i, item in enumerate(high_vol_symbols, 1):
        symbol_ws = item['symbol']  # 例如: BTCUSDT
        symbol_ccxt = f"{symbol_ws[:-4]}/USDT"  # 转换为 ccxt 格式: BTC/USDT
        
        print(f"\n[{i}/{len(high_vol_symbols)}] 分析 {symbol_ccxt}...")
        print(f"  当前价格: {item['current_price']:.8f}")
        print(f"  最大波动: {item['max_change']:.2f}%")
        
        try:
            # 获取K线数据
            ohlcv_df = fetch_ohlcv(symbol_ccxt, timeframe)
            
            # 生成分析报告
            post = generate_post(symbol_ccxt, timeframe, ohlcv_df)
            
            # 保存报告，包含波动率信息
            extra_data = {
                'volatility': {
                    'max_change': item['max_change'],
                    'changes': item['changes'],
                    'current_price': item['current_price'],
                    'volume_24h': item['volume_24h'],
                    'quote_volume': item['quote_volume'],
                }
            }
            save_post(symbol_ccxt, post, extra_data)
            
            print(f"  ✓ 分析完成")
            
            # 避免API限流
            if i < len(high_vol_symbols):
                time.sleep(2)
                
        except Exception as e:
            print(f"  ✗ 分析失败: {e}")
            continue
    
    print(f"\n{'='*60}")
    print("分析完成！")
    print(f"{'='*60}")


monitor = BinanceTickerMonitor(volatility_threshold=5.0)

def main():
    monitor.start()
    time.sleep(3)
    while True:
        symbols = monitor.get_high_volatility_symbols()

        for symbol in symbols[:20]:
            symbol_name = symbol['symbol']
            timeframe = "1h"
            ohlcv_df = fetch_ohlcv(symbol_name, timeframe)
            post = generate_post(symbol_name, timeframe, ohlcv_df)
            save_post(symbol_name, post)

if __name__ == "__main__":
    main()
