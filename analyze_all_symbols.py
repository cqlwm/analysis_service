"""
分析币安所有交易对
"""
import ccxt
import dotenv
import pandas as pd
import json
import time
from datetime import datetime

dotenv.load_dotenv()

from llm_enhanced_strategy import llm_enhanced_strategy, print_enhanced_signal

# 过滤不需要的交易对类型
EXCLUDE_PATTERNS = [
    'DOWN/', 'UP/', 'BEAR/', 'BULL/',  # 杠杆代币
    'USDC', 'DAI', 'TUSD',             # 稳定币(不含USDT)
    'BRL', 'EUR', 'GBP', 'RUB',        # 法币对
    'CNY', 'JPY', 'KRW',
    'AUD', 'NZD',
    'TRY', 'ZAR',
    'BIDR', 'PAX', 'USDP',             # 稳定币
]


def is_valid_symbol(symbol: str) -> bool:
    """检查交易对是否有效"""
    # 排除模式
    for pattern in EXCLUDE_PATTERNS:
        if pattern in symbol:
            return False
    return True


def get_filtered_symbols(exchange: ccxt.Exchange) -> list[str]:
    """获取过滤后的交易对列表"""
    markets = exchange.load_markets()
    print(f"加载了 {len(markets)} 个市场")

    # 调试：打印前几个symbol格式
    sample_symbols = [s for s in list(markets.keys())[:5]]
    print(f"示例交易对: {sample_symbols}")

    symbols = []
    for symbol in markets.keys():
        # ccxt 返回的格式是 BTC/USDT
        if '/' not in symbol:
            continue
        base, quote = symbol.split('/')
        # 只保留 USDT 现货交易对
        if quote == 'USDT' and markets[symbol].get('spot', False):
            if is_valid_symbol(symbol):
                symbols.append(symbol)

    return sorted(symbols)


def analyze_symbol(exchange: ccxt.Exchange, symbol: str, timeframe: str = '1h', limit: int = 200) -> dict:
    """分析单个交易对"""
    try:
        # 获取K线数据
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

        if len(ohlcv) < 100:  # 需要足够数据
            return {
                'symbol': symbol,
                'status': 'failed',
                'error': f'数据不足: {len(ohlcv)} 条'
            }

        # 转换为DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # 调用LLM增强策略
        result = llm_enhanced_strategy(df, total_capital=10000, enable_llm=True)

        return {
            'symbol': symbol,
            'status': 'success',
            'data_range': f"{df['timestamp'].iloc[0]} ~ {df['timestamp'].iloc[-1]}",
            'signal': result.get('signal', 'UNKNOWN'),
            'llm_analysis': result.get('llm_analysis', {}),
            'full_result': result
        }

    except Exception as e:
        return {
            'symbol': symbol,
            'status': 'failed',
            'error': str(e)
        }


def main():
    # 初始化币安
    exchange = ccxt.binance({
        'enableRateLimit': True,
    })

    print("=" * 80)
    print("📊 币安全交易对 LLM 分析")
    print("=" * 80)

    # 获取交易对列表
    print("正在加载交易对列表...")
    symbols = get_filtered_symbols(exchange)
    print(f"✅ 过滤后共有 {len(symbols)} 个有效交易对")

    # 限制数量（可选）- 减少数量加快速度
    MAX_SYMBOLS = 1000  # 先分析10个测试
    if len(symbols) > MAX_SYMBOLS:
        print(f"⚠️  为了控制时间，限制分析前 {MAX_SYMBOLS} 个交易对")
        symbols = symbols[:MAX_SYMBOLS]

    # 收集结果
    results = []
    buy_signals = []
    sell_signals = []
    hold_signals = []

    print(f"\n🚀 开始分析 {len(symbols)} 个交易对...")
    print("-" * 80)

    for i, symbol in enumerate(symbols, 1):
        # 进度显示
        progress = f"[{i}/{len(symbols)}]"
        print(f"{progress} 正在分析: {symbol}", end=' ')

        # 分析
        result = analyze_symbol(exchange, symbol)

        # 分类保存
        if result['status'] == 'success':
            signal = result['signal']
            print(f"✅ {signal}")
            results.append(result)

            if signal == 'BUY':
                buy_signals.append(result)
            elif signal == 'SELL':
                sell_signals.append(result)
            else:
                hold_signals.append(result)
        else:
            print(f"❌ {result.get('error', '未知错误')}")

        # 避免触发API限流
        time.sleep(1.5)

    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"analysis_results_{timestamp}.json"

    all_results = {
        'timestamp': timestamp,
        'total_symbols': len(symbols),
        'analyzed': len(results),
        'buy_signals': [r['symbol'] for r in buy_signals],
        'sell_signals': [r['symbol'] for r in sell_signals],
        'hold_signals': [r['symbol'] for r in hold_signals],
        'results': results
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    # 打印汇总
    print("\n" + "=" * 80)
    print("📊 分析汇总")
    print("=" * 80)
    print(f"总交易对数: {len(symbols)}")
    print(f"成功分析: {len(results)}")
    print(f"买入信号: {len(buy_signals)} - {', '.join([r['symbol'] for r in buy_signals[:10]])}")
    print(f"卖出信号: {len(sell_signals)} - {', '.join([r['symbol'] for r in sell_signals[:10]])}")
    print(f"观望信号: {len(hold_signals)}")
    print("-" * 80)
    print(f"📁 详细结果已保存至: {output_file}")
    print("=" * 80)

    # 打印买入信号的详细信息
    if buy_signals:
        print("\n🟢 买入信号详情:")
        for result in buy_signals[:5]:  # 只显示前5个
            print(f"\n{result['symbol']}:")
            if 'llm_analysis' in result:
                analysis = result['llm_analysis']
                print(f"  - 阶段: {analysis.get('market_phase', 'N/A')}")
                print(f"  - 趋势: {analysis.get('trend_strength', 'N/A')}")
                print(f"  - 情绪: {analysis.get('sentiment', 'N/A')}")
                print(f"  - 置信度: {analysis.get('confidence', 0):.0%}")

    return all_results


if __name__ == "__main__":
    main()
