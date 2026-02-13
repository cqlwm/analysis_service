"""
Binance 合约市场 Ticker 监控器
订阅合约市场所有交易对的完整Ticker(!ticker@arr)，计算多周期涨跌幅，过滤高波动率交易对
特点：24小时涨跌幅直接使用币安官方数据(P字段)，其他周期通过历史价格计算
"""

import json
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import websocket
import threading


class BinanceTickerMonitor:
    """Binance合约市场Ticker监控器"""
    
    # 使用合约市场WebSocket - !ticker@arr 返回完整24小时ticker数据（包含P字段：24h涨跌幅百分比）
    WS_URL = "wss://fstream.binance.com/ws/!ticker@arr"
    
    # 时间窗口配置 (秒)
    TIME_WINDOWS = {
        '5m': 5 * 60,
        '15m': 15 * 60,
        '1h': 60 * 60,
        '4h': 4 * 60 * 60,
        '24h': 24 * 60 * 60,
    }
    
    def __init__(self, volatility_threshold: float = 5.0):
        """
        初始化监控器
        
        Args:
            volatility_threshold: 波动率阈值（百分比），超过此值认为是高波动率
        """
        self.ws_thread = None
        self.volatility_threshold = volatility_threshold
        
        # 价格历史记录: {symbol: [(timestamp, price), ...]}
        self.price_history: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        
        # 最新ticker数据: {symbol: ticker_data}
        self.latest_tickers: Dict[str, dict] = {}
        
        # 统计数据
        self.stats = {
            'total_symbols': 0,
            'high_volatility_count': 0,
            'last_update': None,
        }
        
        self.ws = None
        self.running = False
        self._lock = threading.RLock()
        
    def _clean_old_data(self, symbol: str, current_time: float):
        """清理过期的历史数据"""
        max_window = max(self.TIME_WINDOWS.values())
        cutoff_time = current_time - max_window
        
        if symbol in self.price_history:
            self.price_history[symbol] = [
                (ts, price) for ts, price in self.price_history[symbol]
                if ts >= cutoff_time
            ]
    
    def _calculate_price_change(self, symbol: str, window_seconds: float, current_time: float, current_price: float) -> Optional[float]:
        """
        计算指定时间窗口的价格变化百分比
        
        Returns:
            涨跌幅百分比，如果没有足够数据则返回None
        """
        if symbol not in self.price_history or not self.price_history[symbol]:
            return None
        
        target_time = current_time - window_seconds
        history = self.price_history[symbol]
        
        # 找到最接近目标时间的价格
        closest_price = None
        closest_diff = float('inf')
        
        for ts, price in history:
            diff = abs(ts - target_time)
            if diff < closest_diff:
                closest_diff = diff
                closest_price = price
        
        # 如果数据太旧（超过窗口时间的1.5倍），返回None
        if closest_diff > window_seconds * 1.5 or closest_price is None:
            return None
        
        return ((current_price - closest_price) / closest_price) * 100
    
    def _update_price_history(self, symbol: str, price: float, timestamp: float):
        """更新价格历史"""
        self.price_history[symbol].append((timestamp, price))
        self._clean_old_data(symbol, timestamp)
    
    def calculate_all_changes(self, symbol: str) -> Dict[str, Optional[float]]:
        """
        计算所有时间窗口的涨跌幅
        - 5m, 15m, 1h, 4h: 通过历史价格计算
        - 24h: 直接使用币安返回的P字段（24小时价格变化百分比）

        Returns:
            {时间窗口: 涨跌幅百分比}
        """
        with self._lock:
            if symbol not in self.latest_tickers:
                return {k: None for k in self.TIME_WINDOWS.keys()}

            ticker = self.latest_tickers[symbol]
            current_price = float(ticker['c'])
            current_time = time.time()

            changes = {}
            for window_name, window_seconds in self.TIME_WINDOWS.items():
                if window_name == '24h':
                    # 24小时涨跌幅直接使用币安返回的数据（更精确）
                    changes[window_name] = float(ticker.get('P', 0))
                else:
                    # 其他时间窗口通过历史价格计算
                    change = self._calculate_price_change(symbol, window_seconds, current_time, current_price)
                    changes[window_name] = change

            return changes
    
    def get_high_volatility_symbols(self) -> List[dict]:
        """
        获取高波动率交易对
        
        Returns:
            按波动率排序的高波动率交易对列表
        """
        high_vol_symbols = []
        with self._lock:
            for symbol, ticker in self.latest_tickers.items():
                changes = self.calculate_all_changes(symbol)
                
                # 检查是否有任何时间窗口超过阈值
                max_change = max(
                    (abs(v) for v in changes.values() if v is not None),
                    default=0
                )
                
                if max_change >= self.volatility_threshold:
                    high_vol_symbols.append({
                        'symbol': symbol,
                        'current_price': float(ticker['c']),
                        'changes': changes,
                        'max_change': max_change,
                        'volume_24h': float(ticker.get('v', 0)),
                        'quote_volume': float(ticker.get('q', 0)),
                    })
        
        # 按最大波动率排序
        high_vol_symbols.sort(key=lambda x: x['max_change'], reverse=True)
        return high_vol_symbols
    
    def _on_message(self, ws, message):
        """处理WebSocket消息"""
        try:
            data = json.loads(message)
            
            # !ticker@arr 返回的是数组，包含完整的24小时统计数据（含P字段：24h涨跌幅百分比）
            if isinstance(data, list):
                current_time = time.time()
                
                with self._lock:
                    for ticker in data:
                        symbol = ticker['s']
                        price = float(ticker['c'])
                        
                        # 更新价格历史
                        self._update_price_history(symbol, price, current_time)
                        
                        # 保存最新ticker
                        self.latest_tickers[symbol] = ticker
                    
                    self.stats['total_symbols'] = len(self.latest_tickers)
                    self.stats['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
        except Exception as e:
            print(f"处理消息时出错: {e}")
    
    def _on_error(self, ws, error):
        """处理错误"""
        print(f"WebSocket错误: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭时"""
        print(f"WebSocket连接关闭: {close_status_code} - {close_msg}")
        self.running = False
    
    def _on_open(self, ws):
        """连接打开时"""
        print("WebSocket连接已建立，开始接收数据...")
        self.running = True
    
    def start(self):
        """启动监控"""
        print(f"正在连接到 {self.WS_URL}...")
        
        self.ws = websocket.WebSocketApp(
            self.WS_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        # 在后台线程运行WebSocket
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()
    
    def stop(self):
        """停止监控"""
        self.running = False
        if self.ws:
            self.ws.close()
        print("监控器已停止")
    
    def print_stats(self):
        """打印统计信息"""
        print(f"\n{'='*60}")
        print(f"监控统计 - {self.stats['last_update']}")
        print(f"交易对数量: {self.stats['total_symbols']}")
        print(f"高波动率交易对数量: {len(self.get_high_volatility_symbols())}")
        print(f"{'='*60}")
    
    def print_high_volatility(self, top_n: int = 20):
        """
        打印高波动率交易对
        
        Args:
            top_n: 显示前N个
        """
        high_vol = self.get_high_volatility_symbols()
        
        if not high_vol:
            print(f"\n暂无明显波动（阈值: {self.volatility_threshold}%）")
            return
        
        print(f"\n{'='*120}")
        print(f"高波动率交易对 (阈值: {self.volatility_threshold}%) - 共 {len(high_vol)} 个")
        print(f"{'='*120}")
        print(f"{'排名':<6}{'交易对':<12}{'当前价格':<15}{'最大波动':<12}{'5分钟':<10}{'15分钟':<10}{'1小时':<10}{'4小时':<10}{'24小时':<10}")
        print(f"{'-'*120}")
        
        for i, item in enumerate(high_vol[:top_n], 1):
            changes = item['changes']
            row = (
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
            print(row)
        
        print(f"{'='*120}")


def main():
    """主函数"""
    import signal
    import sys
    
    # 创建监控器，设置波动率阈值为3%
    monitor = BinanceTickerMonitor(volatility_threshold=3.0)
    
    # 处理Ctrl+C
    def signal_handler(sig, frame):
        print('\n正在停止...')
        monitor.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # 启动监控
    monitor.start()
    
    # 等待连接建立
    print("等待连接...")
    time.sleep(3)
    
    try:
        while True:
            monitor.print_stats()
            monitor.print_high_volatility(top_n=20)
            
            # 每30秒刷新一次
            time.sleep(30)
            
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop()


if __name__ == "__main__":
    main()
