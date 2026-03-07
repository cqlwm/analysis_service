import argparse
import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import ccxt

from symbol import Symbol


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


def parse_fetched_at_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_ccxt_symbol(raw_symbol: str) -> str:
    return Symbol.parse(raw_symbol).ccxt


def build_exchange() -> ccxt.binance:
    exchange = ccxt.binance(
        {
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
            },
        }
    )
    exchange.load_markets()
    return exchange


def fetch_exit_price_1m_close(
    exchange: ccxt.binance,
    symbol: str,
    target_timestamp_ms: int,
) -> float | None:
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe="1m", since=target_timestamp_ms, limit=1)
    except Exception:
        return None

    if not candles:
        return None

    first = candles[0]
    if len(first) < 5:
        return None
    close_price = to_float(first[4])
    if close_price <= 0:
        return None
    return close_price


def load_rows(input_path: Path) -> list[dict[str, str]]:
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    with input_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def calc_24h_pnl(
    rows: list[dict[str, str]],
    invest_usdt: float,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        fetched_at = row.get("fetched_at_utc", "").strip()
        if fetched_at:
            grouped[fetched_at].append(row)

    exchange = build_exchange()
    now = datetime.now(timezone.utc)
    exit_price_cache: dict[tuple[str, int], float | None] = {}
    results: list[dict[str, Any]] = []

    for fetched_at, batch_rows in sorted(grouped.items(), key=lambda x: x[0]):
        fetched_dt = parse_fetched_at_utc(fetched_at)
        exit_dt = fetched_dt + timedelta(hours=24)
        exit_ms = int(exit_dt.timestamp() * 1000)

        batch_results: list[dict[str, Any]] = []
        sorted_rows = sorted(batch_rows, key=lambda r: to_int(r.get("rank")))

        for row in sorted_rows:
            symbol_raw = row.get("symbol", "")
            entry_price = to_float(row.get("last_price"))
            rank = to_int(row.get("rank"))

            result: dict[str, Any] = {
                "fetched_at_utc": fetched_at,
                "rank": rank,
                "symbol": symbol_raw,
                "entry_price": round(entry_price, 12) if entry_price > 0 else "",
                "exit_price": "",
                "invest_usdt": round(invest_usdt, 8),
                "quantity": "",
                "pnl_usdt": "",
                "pnl_pct": "",
                "exit_at_utc": exit_dt.isoformat(),
                "status": "ok",
            }

            if entry_price <= 0:
                result["status"] = "invalid_entry_price"
                batch_results.append(result)
                continue

            if now < exit_dt:
                result["status"] = "pending_24h"
                batch_results.append(result)
                continue

            ccxt_symbol = to_ccxt_symbol(symbol_raw)
            cache_key = (ccxt_symbol, exit_ms)
            if cache_key not in exit_price_cache:
                exit_price_cache[cache_key] = fetch_exit_price_1m_close(exchange, ccxt_symbol, exit_ms)
            exit_price = exit_price_cache[cache_key]

            if exit_price is None:
                result["status"] = "missing_exit_price"
                batch_results.append(result)
                continue

            quantity = invest_usdt / entry_price
            pnl_usdt = (exit_price - entry_price) * quantity
            pnl_pct = (exit_price / entry_price - 1) * 100

            result["exit_price"] = round(exit_price, 12)
            result["quantity"] = round(quantity, 12)
            result["pnl_usdt"] = round(pnl_usdt, 8)
            result["pnl_pct"] = round(pnl_pct, 6)
            batch_results.append(result)

        batch_size = len(batch_results)
        resolved_count = sum(1 for r in batch_results if r["status"] == "ok")
        batch_total_pnl = round(sum(to_float(r.get("pnl_usdt")) for r in batch_results), 8)
        batch_total_investment = round(invest_usdt * batch_size, 8)
        batch_total_return_pct = (
            round(batch_total_pnl / batch_total_investment * 100, 6)
            if batch_total_investment > 0
            else 0.0
        )

        for result in batch_results:
            result["batch_size"] = batch_size
            result["batch_resolved_count"] = resolved_count
            result["batch_total_pnl_usdt"] = batch_total_pnl
            result["batch_total_investment_usdt"] = batch_total_investment
            result["batch_total_return_pct"] = batch_total_return_pct
            results.append(result)

    return results


def save_results(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "fetched_at_utc",
        "rank",
        "symbol",
        "entry_price",
        "exit_price",
        "invest_usdt",
        "quantity",
        "pnl_usdt",
        "pnl_pct",
        "exit_at_utc",
        "status",
        "batch_size",
        "batch_resolved_count",
        "batch_total_pnl_usdt",
        "batch_total_investment_usdt",
        "batch_total_return_pct",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="计算涨幅榜每个币做多 100 USDT 在 24 小时后的盈亏，并输出 CSV"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/top_gainers.csv"),
        help="输入 CSV 路径，默认 data/top_gainers.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/top_gainers_24h_pnl.csv"),
        help="输出 CSV 路径，默认 data/top_gainers_24h_pnl.csv",
    )
    parser.add_argument(
        "--invest-usdt",
        type=float,
        default=100.0,
        help="每个币做多投入金额（USDT），默认 100",
    )
    args = parser.parse_args()

    source_rows = load_rows(args.input)
    result_rows = calc_24h_pnl(source_rows, invest_usdt=args.invest_usdt)
    save_results(result_rows, args.output)

    print(f"已保存 {len(result_rows)} 条记录到: {args.output}")


if __name__ == "__main__":
    main()
