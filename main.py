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

from alpha_trend_strategy import AlphaTrendStrategy, generate_flash_prompt, generate_indicator_prompt

dotenv.load_dotenv()

def fetch_ohlcv(symbol:str, timeframe: str='1h') -> DataFrame:
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

def generate_post(symbol:str, timeframe: str, df: DataFrame):

    strategy = AlphaTrendStrategy()
    df = strategy.calculate_indicators(df)
    summary = strategy.generate_indicator_summary(df)
    indicator_prompt = generate_indicator_prompt(
        symbol=symbol,
        timeframe=timeframe,
        data_range=f'{df['timestamp'].iloc[0]} ~ {df['timestamp'].iloc[-1]}',
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
        ChatCompletionSystemMessageParam(content="你是一个专业的加密货币交易分析员, 擅长分析技术指标和市场趋势, 并根据指标生成专业的交易分析报告。", role="system"),
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

def save_post(symbol: str, post: str):
    symbol = symbol.replace('/USDT', '')
    timestamp = int(time.time())
    with open(f'data/{symbol}_{timestamp}.json', 'w') as f:
        f.write(json.dumps({
            'symbols': [symbol],
            'content': post,
        }, indent=4, ensure_ascii=False))

def main():
    symbol='COLLECT/USDT'
    timeframe='1h'
    ohlcv_df = fetch_ohlcv(symbol, timeframe)
    post = generate_post(symbol, timeframe, ohlcv_df)
    save_post(symbol, post)

if __name__ == "__main__":
    main()