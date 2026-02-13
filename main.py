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
from binance_ticker_monitor import BinanceTickerMonitor

dotenv.load_dotenv()

# 初始化OpenAI客户端
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_API_BASE_URL", "https://api.siliconflow.cn/v1")
model_name = os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3.2")
min_model_name = os.getenv("MIN_MODEL_NAME", "Qwen/Qwen3-8B")

if not api_key:
    raise ValueError("OPENAI_API_KEY not set")

client = openai.OpenAI(api_key=api_key, base_url=base_url)

exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
    },
})
exchange.load_markets()

CACHE_DIR = "data/cache"
LAST_GEN_FILE = f"{CACHE_DIR}/last_generation.json"

def load_last_generation_time():
    if os.path.exists(LAST_GEN_FILE):
        with open(LAST_GEN_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_last_generation_time(data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(LAST_GEN_FILE, 'w') as f:
        json.dump(data, f)


def fetch_ohlcv(symbol: str, timeframe: str = '1h') -> DataFrame:
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
        # extra_body={
        #     'enable_thinking': True
        # }
    )
    final_post = response2.choices[0].message.content or ""

    return final_post


def extract_signal_json(symbol: str, post_content: str) -> dict | None:
    """从生成的post中提取交易信号JSON"""
    symbol_clean = symbol.removesuffix('USDT').removesuffix('/')
    
    extract_prompt = f"""从以下交易信号文章中提取关键交易信息，输出纯JSON格式，不要包含任何其他内容。

文章内容：
{post_content}

请提取以下格式的JSON：
{{
    "symbol": "{symbol_clean}",
    "position_direction": "short" 或 "long",
    "entry_price": [最小入场价, 最大入场价],
    "stop_loss_price": 止损价,
    "take_profit_price": [止盈价1, 止盈价2, 止盈价3]
}}

注意：
- entry_price 是一个数组，表示入场价格区间
- take_profit_price 是一个数组，最多3个止盈位
- position_direction: 做空用"short"，做多用"long"
- 如果无法提取某字段，用null表示
"""

    messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(content="你是一个专业的交易信号提取助手，擅长从文本中提取结构化的交易信息。", role="system"),
        ChatCompletionUserMessageParam(content=extract_prompt, role="user"),
    ]

    try:
        from openai.types.shared_params.response_format_json_object import ResponseFormatJSONObject
        response = client.chat.completions.create(
            model=min_model_name,
            messages=messages,
            max_tokens=500,
            extra_body={
                "enable_thinking": False
            },
            response_format=ResponseFormatJSONObject(type="json_object")
        )
        result = response.choices[0].message.content or ""
        if len(result) > 2 and result[0] == "{" and result[-1] == "}":
            return json.loads(result)
    except Exception as e:
        print(f"提取JSON信号失败: {e}")
    
    return None


def save_signals_to_csv(signal_json: dict, timestamp: int):
    """将信号JSON保存到CSV文件"""
    import csv
    
    csv_file = "data/cache/signals.csv"
    file_exists = os.path.exists(csv_file)
    
    # 展开entry_price数组
    entry_prices = signal_json.get("entry_price", [])
    entry_price_min = entry_prices[0] if len(entry_prices) > 0 else ""
    entry_price_max = entry_prices[1] if len(entry_prices) > 1 else entry_price_min
    
    # 展开take_profit_price数组
    take_profits = signal_json.get("take_profit_price", [])
    take_profit_1 = take_profits[0] if len(take_profits) > 0 else ""
    take_profit_2 = take_profits[1] if len(take_profits) > 1 else ""
    take_profit_3 = take_profits[2] if len(take_profits) > 2 else ""
    
    row = {
        "timestamp": timestamp,
        "symbol": signal_json.get("symbol", ""),
        "position_direction": signal_json.get("position_direction", ""),
        "entry_price_min": entry_price_min,
        "entry_price_max": entry_price_max,
        "stop_loss_price": signal_json.get("stop_loss_price", ""),
        "take_profit_1": take_profit_1,
        "take_profit_2": take_profit_2,
        "take_profit_3": take_profit_3,
    }
    
    fieldnames = ["timestamp", "symbol", "position_direction", "entry_price_min", "entry_price_max", 
                  "stop_loss_price", "take_profit_1", "take_profit_2", "take_profit_3"]
    
    with open(csv_file, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    
    print(f"✓ 已保存信号到CSV: {csv_file}")


def save_post(symbol: str, post: str):
    """保存分析报告到文件
    
    Args:
        symbol: 交易对符号
        post: 生成的分析报告内容
        signal_json: 提取的交易信号JSON
    """
    symbol_clean = symbol.removesuffix('USDT').removesuffix('/')
    timestamp = int(time.time())
    data = {
        'symbols': [symbol_clean],
        'content': post,
        'timestamp': timestamp,
    }
    
    with open(f'data/{symbol_clean}_{timestamp}.json', 'w') as f:
        f.write(json.dumps(data, indent=4, ensure_ascii=False))
    
    print(f"✓ 已保存: data/{symbol_clean}_{timestamp}.json")
    return data


monitor = BinanceTickerMonitor(volatility_threshold=5.0)

def main():
    last_generation_time = load_last_generation_time()
    monitor.start()
    time.sleep(3)
    while monitor.running:
        symbols = monitor.get_high_volatility_symbols()

        for symbol in symbols[:20]:
            symbol_name = symbol['symbol']
            timeframe = "1h"
            
            current_time = time.time()
            if symbol_name in last_generation_time:
                elapsed = current_time - last_generation_time[symbol_name]
                if elapsed < 3600:
                    print(f"⏭️ 跳过 {symbol_name} (距上次 {int(elapsed)}秒)")
                    continue
            
            try:
                ohlcv_df = fetch_ohlcv(symbol_name, timeframe)

                post_text = generate_post(symbol_name, timeframe, ohlcv_df)
                post_data = save_post(symbol_name, post_text)

                signal_json = extract_signal_json(symbol_name, post_text)
                save_signals_to_csv(signal_json, post_data["timestamp"])
            except Exception as e:
                print(e)
            finally:
                last_generation_time[symbol_name] = current_time
                save_last_generation_time(last_generation_time)

if __name__ == "__main__":
    main()
