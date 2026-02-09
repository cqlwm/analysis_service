import ccxt
import dotenv
import pandas as pd
import openai
import os

dotenv.load_dotenv()

from alpha_trend_strategy import AlphaTrendStrategy, generate_flash_prompt, generate_indicator_prompt



def test_alpha_trend_strategy():
    # 交易所配置
    symbol = 'YALA/USDT'
    timeframe = '1h'
    limit = 350  # 需要足够数据计算指标
    
    # 初始化Binance
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
        },
    })
    
    print(f"📈 交易对: {symbol}")
    print(f"⏰ 时间周期: {timeframe}")
    
    # 获取K线数据
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    
    # 转换为DataFrame
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    print(f"✅ 获取到 {len(df)} 条K线数据")
    data_range = f'{df['timestamp'].iloc[0]} ~ {df['timestamp'].iloc[-1]}'
    print(f"📅 数据范围: {data_range}")


    strategy = AlphaTrendStrategy()
    df = strategy.calculate_indicators(df)
    summary = strategy.generate_indicator_summary(df)
    prompt = generate_indicator_prompt(symbol, timeframe, data_range, summary)

    print(prompt)
    print('='*50)
    
    # 初始化OpenAI客户端
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE_URL")
    model_name = os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3.2")
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    
    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    system_prompt = "你是一个专业的加密货币交易分析员, 擅长分析技术指标和市场趋势, 并根据指标生成专业的交易分析。"
    
    response1 = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2000,
        extra_body={
            'enable_thinking': True
        }
    )
    analysis_result = response1.choices[0].message.content or ""
    
    # ========== 第二次LLM调用：生成快讯 ==========
            
    response2 = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{analysis_result}\n{'='*20}\n{generate_flash_prompt()}"},
        ],
        max_tokens=200,
        extra_body={
            'enable_thinking': True
        }
    )
    final_post = response2.choices[0].message.content or ""
    
    print(analysis_result)
    print('='*50)
    print(final_post)

if __name__ == "__main__":
    test_alpha_trend_strategy()
