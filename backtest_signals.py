import ccxt
import csv
import os
import time
import logging

from logger import setup_logger

logger = setup_logger('backtest_signals')

SIGNAL_FILE = "data/cache/signals.csv"
OUTPUT_FILE = "data/cache/backtest_results.csv"
TIMEFRAME = "1h"
POSITION_SIZE_USDT = 100

exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
    },
})
exchange.load_markets()


def load_signals():
    signals = []
    if not os.path.exists(SIGNAL_FILE):
        logger.warning(f"信号文件不存在: {SIGNAL_FILE}")
        return signals
    
    with open(SIGNAL_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            signals.append(row)
    return signals


def load_existing_results():
    existing = {}
    if not os.path.exists(OUTPUT_FILE):
        return existing
    
    with open(OUTPUT_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['result'] in ('stop_loss', 'take_profit'):
                key = (row['timestamp'], row['symbol'])
                existing[key] = row
    return existing


def fetch_ohlcv_since(symbol, timestamp_ms, limit=500):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, since=timestamp_ms, limit=limit)
        return ohlcv
    except Exception as e:
        logger.error(f"获取K线失败 {symbol}: {e}")
        return []


def backtest_signal(signal):
    symbol = signal['symbol'].upper()
    if not symbol.endswith('USDT'):
        symbol = symbol + '/USDT'
    
    position_direction = signal['position_direction']
    entry_price = float(signal['entry_price_min'])
    stop_loss = float(signal['stop_loss_price'])
    
    take_profits = []
    for i in range(1, 4):
        key = f'take_profit_{i}'
        if signal.get(key) and signal[key]:
            try:
                take_profits.append(float(signal[key]))
            except (ValueError, TypeError):
                pass
    
    if not take_profits:
        return None
    
    take_profits = sorted(take_profits, reverse=(position_direction == 'short'))
    
    signal_timestamp = signal['timestamp']
    ohlcv_data = fetch_ohlcv_since(symbol, signal_timestamp)
    
    if not ohlcv_data:
        return None
    
    result = {
        'timestamp': signal['timestamp'],
        'symbol': signal['symbol'],
        'position_direction': position_direction,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'take_profit': ','.join(map(str, take_profits)),
        'result': 'holding',
        'exit_price': '',
        'exit_timestamp': '',
        'pnl_pct': '',
        'pnl_usdt': '',
    }
    
    for i, (ts, open_price, high, low, close, vol) in enumerate(ohlcv_data):
        if i == 0:
            continue
        
        if position_direction == 'short':
            if high >= stop_loss:
                result['result'] = 'stop_loss'
                result['exit_price'] = stop_loss
                result['exit_timestamp'] = ts
                result['pnl_pct'] = round((entry_price - stop_loss) / entry_price * 100, 2)
                result['pnl_usdt'] = round(POSITION_SIZE_USDT * result['pnl_pct'] / 100, 2)
                break
            
            for tp in take_profits:
                if low <= tp:
                    result['result'] = 'take_profit'
                    result['exit_price'] = tp
                    result['exit_timestamp'] = ts
                    result['pnl_pct'] = round((entry_price - tp) / entry_price * 100, 2)
                    result['pnl_usdt'] = round(POSITION_SIZE_USDT * result['pnl_pct'] / 100, 2)
                    break
            else:
                continue
            break
        
        else:
            if low <= stop_loss:
                result['result'] = 'stop_loss'
                result['exit_price'] = stop_loss
                result['exit_timestamp'] = ts
                result['pnl_pct'] = round((stop_loss - entry_price) / entry_price * 100, 2)
                result['pnl_usdt'] = round(POSITION_SIZE_USDT * result['pnl_pct'] / 100, 2)
                break
            
            for tp in take_profits:
                if high >= tp:
                    result['result'] = 'take_profit'
                    result['exit_price'] = tp
                    result['exit_timestamp'] = ts
                    result['pnl_pct'] = round((tp - entry_price) / entry_price * 100, 2)
                    result['pnl_usdt'] = round(POSITION_SIZE_USDT * result['pnl_pct'] / 100, 2)
                    break
            else:
                continue
            break
    
    if result['result'] == 'holding' and ohlcv_data:
        latest_price = ohlcv_data[-1][4]
        if position_direction == 'short':
            result['exit_price'] = latest_price
            result['pnl_pct'] = round((entry_price - latest_price) / entry_price * 100, 2)
            result['pnl_usdt'] = round(POSITION_SIZE_USDT * result['pnl_pct'] / 100, 2)
        else:
            result['exit_price'] = latest_price
            result['pnl_pct'] = round((latest_price - entry_price) / entry_price * 100, 2)
            result['pnl_usdt'] = round(POSITION_SIZE_USDT * result['pnl_pct'] / 100, 2)
    
    return result


def save_results(results):
    fieldnames = ['timestamp', 'symbol', 'position_direction', 'entry_price', 'stop_loss', 
                  'take_profit', 'result', 'exit_price', 'exit_timestamp', 'pnl_pct', 'pnl_usdt']
    
    with open(OUTPUT_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    logger.info(f"结果已保存到: {OUTPUT_FILE}")


def print_statistics(results):
    total = len(results)
    if total == 0:
        logger.info("没有可统计的结果")
        return
    
    take_profit_count = sum(1 for r in results if r['result'] == 'take_profit')
    stop_loss_count = sum(1 for r in results if r['result'] == 'stop_loss')
    holding_count = sum(1 for r in results if r['result'] == 'holding')
    
    closed = take_profit_count + stop_loss_count
    win_rate = (take_profit_count / closed * 100) if closed > 0 else 0
    
    total_pnl = sum(float(r['pnl_usdt']) for r in results if r['pnl_usdt'])
    
    logger.info("="*50)
    logger.info("回测统计")
    logger.info("="*50)
    logger.info(f"总信号数: {total}")
    logger.info(f"止盈次数: {take_profit_count}")
    logger.info(f"止损次数: {stop_loss_count}")
    logger.info(f"持有中: {holding_count}")
    logger.info(f"已平仓: {closed}")
    logger.info(f"胜率: {win_rate:.2f}%")
    logger.info(f"总盈亏: {total_pnl:.2f} USDT")
    logger.info("="*50)


def main():
    logger.info("加载信号...")
    signals = load_signals()
    logger.info(f"加载了 {len(signals)} 个信号")
    
    existing_results = load_existing_results()
    logger.info(f"已有 {len(existing_results)} 个回测结果 (止盈/止损)")
    
    results = []
    skipped = 0
    for i, signal in enumerate(signals):
        key = (signal['timestamp'], signal['symbol'])
        if key in existing_results:
            skipped += 1
            results.append(existing_results[key])
            logger.debug(f"跳过 [{i+1}/{len(signals)}] {signal['symbol']} (已回测)")
            continue
            
        result = backtest_signal(signal)
        if result:
            results.append(result)
            logger.info(f"回测 [{i+1}/{len(signals)}] {signal['symbol']}... {result['result']} (pnl: {result['pnl_usdt']} USDT)")
        else:
            logger.info(f"跳过 [{i+1}/{len(signals)}] {signal['symbol']} (无K线数据)")
        
        time.sleep(0.3)
    
    logger.info(f"跳过 {skipped} 个已回测信号")
    if results:
        save_results(results)
        print_statistics(results)
    else:
        logger.info("没有生成任何结果")


if __name__ == "__main__":
    main()
