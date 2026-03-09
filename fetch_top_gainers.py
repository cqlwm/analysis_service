import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import time

import ccxt

from symbol import Symbol

"""通过 ccxt 获取 Binance 合约市场 ticker 数据。"""
exchange = ccxt.binance(
    {
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",
        },
    }
)
exchange.load_markets()

def fetch_futures_tickers() -> dict[str, Any]:
    return exchange.fetch_tickers()


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def extract_update_ts_ms(ticker: dict[str, Any]) -> int:
    """提取 ticker 的更新时间戳（毫秒）。"""
    ts = to_int(ticker.get("timestamp"))
    if ts > 0:
        return ts

    info = ticker.get("info", {})
    if isinstance(info, dict):
        for key in ("closeTime", "E", "eventTime", "time"):
            ts = to_int(info.get(key))
            if ts > 0:
                return ts

    return 0


def extract_top_gainers(tickers: dict[str, Any], quote: str, top_n: int, max_age_seconds: int) -> list[dict]:
    """提取合约市场中指定计价币种的涨幅榜前 N。"""
    quote = quote.upper()
    rows: list[dict] = []
    now_ms = int(time.time() * 1000)
    max_age_ms = max_age_seconds * 1000

    for ticker in tickers.values():
        symbol_str = ticker.get("symbol", "")
        if not symbol_str:
            continue

        updated_at_ms = extract_update_ts_ms(ticker)
        if updated_at_ms <= 0:
            continue
        if now_ms - updated_at_ms > max_age_ms:
            continue

        sym = Symbol.parse(symbol_str)
        if sym.quote != quote:
            continue

        change_percent = to_float(ticker.get("percentage"))
        if change_percent == 0.0:
            change_percent = to_float(ticker.get("info", {}).get("priceChangePercent"))

        rows.append(
            {
                "symbol": ticker.get("info", {}).get("symbol", sym.full),
                "base": sym.base,
                "quote": sym.quote,
                "change_percent": change_percent,
                "last_price": to_float(ticker.get("last")),
                "volume": to_float(ticker.get("baseVolume")),
                "quote_volume": to_float(ticker.get("quoteVolume")),
                "open_price": to_float(ticker.get("open")),
                "high_price": to_float(ticker.get("high")),
                "low_price": to_float(ticker.get("low")),
                "trade_count": int(ticker.get("info", {}).get("count", 0) or 0),
                "updated_at_ms": updated_at_ms,
            }
        )

    rows.sort(key=lambda x: x["change_percent"], reverse=True)
    return rows[:top_n]


def save_to_csv(rows: list[dict], output_path: Path):
    """保存涨幅榜结果到本地 CSV。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = output_path.exists()

    fetched_at = datetime.now(timezone.utc).isoformat()
    fieldnames = [
        "rank",
        "fetched_at_utc",
        "symbol",
        "base",
        "quote",
        "change_percent",
        "last_price",
        "open_price",
        "high_price",
        "low_price",
        "volume",
        "quote_volume",
        "trade_count",
        "updated_at_ms",
    ]

    with output_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for index, row in enumerate(rows, start=1):
            writer.writerow(
                {
                    "rank": index,
                    "fetched_at_utc": fetched_at,
                    **row,
                }
            )


def main():
    parser = argparse.ArgumentParser(description="获取涨幅榜前 N 币种并保存到 CSV")
    parser.add_argument("--top", type=int, default=10, help="榜单数量，默认 10")
    parser.add_argument("--quote", type=str, default="USDT", help="计价币种，默认 USDT")
    parser.add_argument(
        "--max-age-seconds",
        type=int,
        default=60,
        help="仅提取最近 N 秒内更新的 ticker，默认 60",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/top_gainers.csv"),
        help="输出 CSV 路径，默认 data/top_gainers.csv",
    )
    args = parser.parse_args()

    tickers = fetch_futures_tickers()
    top_gainers = extract_top_gainers(
        tickers,
        quote=args.quote,
        top_n=args.top,
        max_age_seconds=args.max_age_seconds,
    )
    save_to_csv(top_gainers, args.output)

    print(f"已保存 {len(top_gainers)} 条记录到: {args.output}")


if __name__ == "__main__":
    main()
