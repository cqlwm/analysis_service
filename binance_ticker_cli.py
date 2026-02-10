"""
Binance 合约市场 Ticker 监控器 (增强版)
订阅合约市场所有交易对的 miniTicker，计算多周期涨跌幅，过滤高波动率交易对

使用方法:
    python binance_ticker_cli.py                    # 使用默认设置运行
    python binance_ticker_cli.py --threshold 5      # 设置波动率阈值为5%
    python binance_ticker_cli.py --interval 10      # 每10秒刷新一次
    python binance_ticker_cli.py --output data.json # 导出高波动率交易对到JSON
"""

import json
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

import typer
import websocket
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout


@dataclass
class TickerData:
    """Ticker数据结构"""
    symbol: str
    price: float
    timestamp: float
    open_price: float  # 24小时开盘价
    high_24h: float
    low_24h: float
    volume_24h: float
    quote_volume: float
    
    @property
    def change_24h(self) -> float:
        """24小时涨跌幅"""
        return ((self.price - self.open_price) / self.open_price) * 100 if self.open_price else 0


class BinanceTickerMonitor:
    """Binance合约市场Ticker监控器"""
    
    # 使用合约市场WebSocket
    WS_URL = "wss://fstream.binance.com/ws/!miniTicker@arr"
    
    # 时间窗口配置 (秒: 显示名称)
    TIME_WINDOWS = {
        5 * 60: '5m',
        15 * 60: '15m',
        60 * 60: '1h',
        4 * 60 * 60: '4h',
        24 * 60 * 60: '24h',
    }
    
    def __init__(
        self,
        volatility_threshold: float = 3.0,
        min_volume_24h: float = 0,
        top_n: int = 20,
        output_file: Optional[str] = None
    ):
        self.volatility_threshold = volatility_threshold
        self.min_volume_24h = min_volume_24h
        self.top_n = top_n
        self.output_file = output_file
        
        # 价格历史: {symbol: [(timestamp, price), ...]}
        self.price_history: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        self.latest_tickers: Dict[str, TickerData] = {}
        
        self.stats = {
            'total_symbols': 0,
            'high_volatility_count': 0,
            'last_update': None,
            'start_time': time.time(),
        }
        
        self.ws = None
        self.running = False
        self.console = Console()
        
    def _clean_old_data(self, symbol: str, current_time: float):
        """清理过期数据"""
        max_window = max(self.TIME_WINDOWS.keys())
        cutoff_time = current_time - max_window
        
        if symbol in self.price_history:
            self.price_history[symbol] = [
                (ts, price) for ts, price in self.price_history[symbol]
                if ts >= cutoff_time
            ]
    
    def _calculate_changes(self, symbol: str) -> Dict[str, Optional[float]]:
        """计算所有时间窗口的涨跌幅"""
        if symbol not in self.latest_tickers:
            return {name: None for name in self.TIME_WINDOWS.values()}
        
        current_price = self.latest_tickers[symbol].price
        current_time = time.time()
        changes = {}
        
        for window_seconds, window_name in self.TIME_WINDOWS.items():
            target_time = current_time - window_seconds
            history = self.price_history.get(symbol, [])
            
            closest_price = None
            closest_diff = float('inf')
            
            for ts, price in history:
                diff = abs(ts - target_time)
                if diff < closest_diff:
                    closest_diff = diff
                    closest_price = price
            
            if closest_diff > window_seconds * 1.5 or closest_price is None:
                changes[window_name] = None
            else:
                changes[window_name] = ((current_price - closest_price) / closest_price) * 100
        
        return changes
    
    def get_high_volatility_symbols(self) -> List[dict]:
        """获取高波动率交易对"""
        high_vol = []
        
        for symbol, ticker in self.latest_tickers.items():
            # 过滤低成交量
            if ticker.volume_24h < self.min_volume_24h:
                continue
            
            changes = self._calculate_changes(symbol)
            max_change = max(
                (abs(v) for v in changes.values() if v is not None),
                default=0
            )
            
            if max_change >= self.volatility_threshold:
                high_vol.append({
                    'symbol': symbol,
                    'price': ticker.price,
                    'changes': changes,
                    'max_change': max_change,
                    'volume_24h': ticker.volume_24h,
                    'quote_volume': ticker.quote_volume,
                    'change_24h': ticker.change_24h,
                })
        
        high_vol.sort(key=lambda x: x['max_change'], reverse=True)
        return high_vol
    
    def _on_message(self, ws, message):
        """处理WebSocket消息"""
        try:
            data = json.loads(message)
            current_time = time.time()
            
            if isinstance(data, list):
                for item in data:
                    symbol = item['s']
                    price = float(item['c'])
                    
                    # 更新历史
                    self.price_history[symbol].append((current_time, price))
                    self._clean_old_data(symbol, current_time)
                    
                    # 更新最新数据
                    self.latest_tickers[symbol] = TickerData(
                        symbol=symbol,
                        price=price,
                        timestamp=current_time,
                        open_price=float(item['o']),
                        high_24h=float(item['h']),
                        low_24h=float(item['l']),
                        volume_24h=float(item['v']),
                        quote_volume=float(item['q'])
                    )
                
                self.stats['total_symbols'] = len(self.latest_tickers)
                self.stats['last_update'] = datetime.now()
                
        except Exception as e:
            self.console.print(f"[red]处理消息错误: {e}[/red]")
    
    def _on_error(self, ws, error):
        self.console.print(f"[red]WebSocket错误: {error}[/red]")
    
    def _on_close(self, ws, close_status_code, close_msg):
        self.console.print(f"[yellow]WebSocket关闭: {close_status_code} - {close_msg}[/yellow]")
        self.running = False
    
    def _on_open(self, ws):
        self.console.print("[green]WebSocket连接成功！开始接收数据...[/green]")
        self.running = True
    
    def create_table(self) -> Table:
        """创建Rich表格"""
        table = Table(title="高波动率交易对", show_header=True, header_style="bold magenta")
        
        table.add_column("排名", style="cyan", width=4, justify="center")
        table.add_column("交易对", style="cyan", width=12)
        table.add_column("当前价格", justify="right", width=12)
        table.add_column("最大波动", justify="right", width=10)
        table.add_column("5分钟", justify="right", width=8)
        table.add_column("15分钟", justify="right", width=8)
        table.add_column("1小时", justify="right", width=8)
        table.add_column("4小时", justify="right", width=8)
        table.add_column("24小时", justify="right", width=8)
        table.add_column("24h成交量", justify="right", width=12)
        
        high_vol = self.get_high_volatility_symbols()[:self.top_n]
        
        for i, item in enumerate(high_vol, 1):
            changes = item['changes']
            
            # 格式化涨跌幅颜色
            def fmt_change(val):
                if val is None:
                    return "[dim]--[/dim]"
                color = "green" if val >= 0 else "red"
                return f"[{color}]{val:+.2f}%[/{color}]"
            
            max_change_color = "green" if item['max_change'] >= 0 else "red"
            
            table.add_row(
                str(i),
                item['symbol'],
                f"{item['price']:.8f}" if item['price'] < 1 else f"{item['price']:.4f}",
                f"[{max_change_color}]{item['max_change']:.2f}%[/{max_change_color}]",
                fmt_change(changes.get('5m')),
                fmt_change(changes.get('15m')),
                fmt_change(changes.get('1h')),
                fmt_change(changes.get('4h')),
                fmt_change(changes.get('24h')),
                f"{item['quote_volume']/1e6:.2f}M"
            )
        
        if not high_vol:
            table.add_row("-", f"暂无高波动率交易对 (阈值: {self.volatility_threshold}%)", "", "", "", "", "", "", "", "")
        
        return table
    
    def create_stats_panel(self) -> Panel:
        """创建统计面板"""
        uptime = time.time() - self.stats['start_time']
        high_vol_count = len(self.get_high_volatility_symbols())
        
        content = (
            f"[bold]交易对数量:[/] {self.stats['total_symbols']}\n"
            f"[bold]高波动率:[/] {high_vol_count}\n"
            f"[bold]运行时间:[/] {int(uptime // 60)}分{int(uptime % 60)}秒\n"
            f"[bold]最后更新:[/] {self.stats['last_update'].strftime('%H:%M:%S') if self.stats['last_update'] else '--'}"
        )
        
        return Panel(content, title="统计信息", border_style="blue")
    
    def export_to_json(self):
        """导出高波动率交易对到JSON"""
        if not self.output_file:
            return
        
        high_vol = self.get_high_volatility_symbols()
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'threshold': self.volatility_threshold,
            'count': len(high_vol),
            'symbols': high_vol
        }
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)
        
        self.console.print(f"[green]已导出到: {self.output_file}[/green]")
    
    def start(self):
        """启动监控"""
        self.ws = websocket.WebSocketApp(
            self.WS_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        # 在后台线程运行
        import threading
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()
    
    def stop(self):
        """停止监控"""
        self.running = False
        if self.ws:
            self.ws.close()


app = typer.Typer(help="Binance全市场Ticker监控器")


@app.command()
def monitor(
    threshold: float = typer.Option(3.0, "--threshold", "-t", help="波动率阈值（百分比）"),
    interval: int = typer.Option(30, "--interval", "-i", help="刷新间隔（秒）"),
    min_volume: float = typer.Option(0, "--min-volume", "-v", help="最小24小时成交量过滤"),
    top_n: int = typer.Option(20, "--top", "-n", help="显示前N个高波动率交易对"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="导出结果到JSON文件"),
):
    """启动Binance全市场Ticker监控"""
    
    console = Console()
    
    monitor = BinanceTickerMonitor(
        volatility_threshold=threshold,
        min_volume_24h=min_volume,
        top_n=top_n,
        output_file=output
    )
    
    def signal_handler(sig, frame):
        console.print("\n[yellow]正在停止...[/yellow]")
        monitor.stop()
        if output:
            monitor.export_to_json()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    console.print(f"[bold blue]启动监控...[/bold blue]")
    console.print(f"阈值: {threshold}% | 刷新间隔: {interval}秒 | 最小成交量: {min_volume}")
    
    monitor.start()
    
    # 等待连接
    time.sleep(3)
    
    try:
        with Live(console=console, refresh_per_second=1) as live:
            while True:
                # 创建布局
                layout = Layout()
                
                # 创建表格和统计面板
                table = monitor.create_table()
                stats = monitor.create_stats_panel()
                
                # 分割布局
                layout.split_column(
                    Layout(stats, size=6),
                    Layout(table)
                )
                
                live.update(layout)
                
                # 导出到文件（如果指定）
                if output and monitor.stats['last_update']:
                    monitor.export_to_json()
                
                time.sleep(interval)
                
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop()
        if output:
            monitor.export_to_json()


@app.command()
def quick_scan(
    threshold: float = typer.Option(5.0, "--threshold", "-t", help="波动率阈值"),
    duration: int = typer.Option(60, "--duration", "-d", help="扫描持续时间（秒）"),
):
    """快速扫描当前高波动率交易对"""
    
    console = Console()
    monitor = BinanceTickerMonitor(volatility_threshold=threshold)
    
    console.print(f"[bold blue]开始快速扫描，持续 {duration} 秒...[/bold blue]")
    
    monitor.start()
    time.sleep(3)  # 等待连接和数据收集
    
    try:
        # 倒计时
        for remaining in range(duration - 3, 0, -1):
            console.print(f"收集数据中... {remaining}秒", end="\r")
            time.sleep(1)
        
        console.print("\n")
        
        # 显示结果
        table = monitor.create_table()
        console.print(table)
        
        high_vol = monitor.get_high_volatility_symbols()
        console.print(f"\n[bold]发现 {len(high_vol)} 个高波动率交易对[/bold]")
        
    finally:
        monitor.stop()


if __name__ == "__main__":
    app()
