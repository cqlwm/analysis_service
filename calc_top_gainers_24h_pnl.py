import argparse
import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Tuple

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


def normalize_fetched_at_utc(value: str) -> str:
    dt = parse_fetched_at_utc(value)
    return dt.replace(minute=0, second=0, microsecond=0).isoformat()


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


def fetch_hourly_prices_range(
    exchange: ccxt.binance,
    symbol: str,
    start_timestamp_ms: int,
    end_timestamp_ms: int,
) -> list[tuple[int, float]]:
    if end_timestamp_ms < start_timestamp_ms:
        return []

    points_by_ts: dict[int, float] = {}
    since = start_timestamp_ms
    step_ms = 60 * 60 * 1000

    while since <= end_timestamp_ms:
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe="1h", since=since, limit=1000)
        except Exception:
            break

        if not candles:
            break

        last_ts = to_int(candles[-1][0])
        for candle in candles:
            if len(candle) < 5:
                continue
            ts = to_int(candle[0])
            if ts < start_timestamp_ms or ts > end_timestamp_ms:
                continue
            close_price = to_float(candle[4])
            if close_price <= 0:
                continue
            points_by_ts[ts] = close_price

        if last_ts <= since:
            break
        if last_ts >= end_timestamp_ms:
            break
        since = last_ts + step_ms

    return sorted(points_by_ts.items(), key=lambda item: item[0])


def fetch_current_price(exchange: ccxt.binance, symbol: str) -> float | None:
    try:
        ticker = exchange.fetch_ticker(symbol)
    except Exception:
        return None

    last_price = to_float(ticker.get("last"))
    if last_price <= 0:
        last_price = to_float(ticker.get("close"))
    if last_price <= 0:
        return None
    return last_price


def build_hourly_price_cache(
    exchange: ccxt.binance,
    rows: list[dict[str, str]],
) -> dict[str, list[tuple[int, float]]]:
    symbol_ranges: dict[str, tuple[int, int]] = {}
    horizon_ms = 24 * 60 * 60 * 1000
    padding_ms = 60 * 60 * 1000

    for row in rows:
        fetched_at = row.get("fetched_at_utc", "").strip()
        symbol_raw = row.get("symbol", "").strip()
        if not fetched_at or not symbol_raw:
            continue
        fetched_dt = parse_fetched_at_utc(fetched_at)
        fetched_ms = int(fetched_dt.timestamp() * 1000)
        range_end = fetched_ms + horizon_ms + padding_ms
        symbol = to_ccxt_symbol(symbol_raw)

        if symbol in symbol_ranges:
            old_start, old_end = symbol_ranges[symbol]
            symbol_ranges[symbol] = (min(old_start, fetched_ms), max(old_end, range_end))
        else:
            symbol_ranges[symbol] = (fetched_ms, range_end)

    price_cache: dict[str, list[tuple[int, float]]] = {}

    total_symbols = len(symbol_ranges)
    symbols: Iterator[Tuple[int, str]] = enumerate(sorted(symbol_ranges.keys()), start=1)
    for index, symbol in symbols:
        start_ms, end_ms = symbol_ranges[symbol]
        print(f"预加载K线: {index}/{total_symbols} {symbol}", flush=True)
        price_cache[symbol] = fetch_hourly_prices_range(exchange, symbol, start_ms, end_ms)
    return price_cache


def pick_first_price_at_or_after(
    points: list[tuple[int, float]],
    target_timestamp_ms: int,
) -> float | None:
    left = 0
    right = len(points)
    while left < right:
        mid = (left + right) // 2
        mid_ts = points[mid][0]
        if mid_ts == target_timestamp_ms:
            left = mid
            break
        if mid_ts < target_timestamp_ms:
            left = mid + 1
        else:
            right = mid

    if left >= len(points):
        return None
    return points[left][1]


def load_rows(input_path: Path) -> list[dict[str, str]]:
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    with input_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def calc_24h_pnl(
    rows: list[dict[str, str]],
    invest_usdt: float,
    exchange: ccxt.binance,
    hourly_price_cache: dict[str, list[tuple[int, float]]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        fetched_at = row.get("fetched_at_utc", "").strip()
        if fetched_at:
            grouped[fetched_at].append(row)

    now = datetime.now(timezone.utc)
    current_price_cache: dict[str, float | None] = {}
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
                "entry_price": entry_price,
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

            ccxt_symbol = to_ccxt_symbol(symbol_raw)

            if now < exit_dt:
                if ccxt_symbol not in current_price_cache:
                    current_price_cache[ccxt_symbol] = fetch_current_price(exchange, ccxt_symbol)
                current_price = current_price_cache[ccxt_symbol]

                if current_price is None:
                    result["status"] = "missing_current_price"
                    batch_results.append(result)
                    continue

                quantity = invest_usdt / entry_price
                pnl_usdt = (current_price - entry_price) * quantity
                pnl_pct = (current_price / entry_price - 1) * 100

                result["exit_at_utc"] = now.isoformat()
                result["exit_price"] = round(current_price, 12)
                result["quantity"] = round(quantity, 12)
                result["pnl_usdt"] = round(pnl_usdt, 8)
                result["pnl_pct"] = round(pnl_pct, 6)
                result["status"] = "ok_realtime"
                batch_results.append(result)
                continue

            hourly_points = hourly_price_cache.get(ccxt_symbol, [])
            exit_price = pick_first_price_at_or_after(hourly_points, exit_ms)

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
        resolved_count = sum(1 for r in batch_results if r["status"] in {"ok", "ok_realtime"})
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


def calc_hourly_batch_pnl(
    rows: list[dict[str, str]],
    invest_usdt: float,
    exchange: ccxt.binance,
    hourly_price_cache: dict[str, list[tuple[int, float]]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        fetched_at = row.get("fetched_at_utc", "").strip()
        if fetched_at:
            grouped[fetched_at].append(row)

    now = datetime.now(timezone.utc)
    current_price_cache: dict[str, float | None] = {}
    results: list[dict[str, Any]] = []

    sorted_groups = sorted(grouped.items(), key=lambda x: x[0])
    total_groups = len(sorted_groups)
    for batch_index, (fetched_at, batch_rows) in enumerate(sorted_groups, start=1):
        fetched_dt = parse_fetched_at_utc(fetched_at)
        sorted_rows = sorted(batch_rows, key=lambda r: to_int(r.get("rank")))
        batch_size = len(sorted_rows)

        hour_count = 24
        hourly_total_pnl: list[float] = [0.0] * hour_count
        hourly_resolved_count: list[int] = [0] * hour_count
        hourly_missing_price_count: list[int] = [0] * hour_count
        hourly_invalid_entry_count: list[int] = [0] * hour_count

        print(f"处理中: batch {batch_index}/{total_groups} @ {fetched_at}", flush=True)

        for row in sorted_rows:
            symbol_raw = row.get("symbol", "")
            entry_price = to_float(row.get("last_price"))
            if entry_price <= 0:
                for i in range(hour_count):
                    hourly_invalid_entry_count[i] += 1
                continue

            ccxt_symbol = to_ccxt_symbol(symbol_raw)
            hourly_points = hourly_price_cache.get(ccxt_symbol, [])

            current_price: float | None = None
            for hour_offset in range(1, hour_count + 1):
                index = hour_offset - 1
                target_dt = fetched_dt + timedelta(hours=hour_offset)
                target_ms = int(target_dt.timestamp() * 1000)

                exit_price: float | None = None
                if now < target_dt:
                    if current_price is None:
                        if ccxt_symbol not in current_price_cache:
                            current_price_cache[ccxt_symbol] = fetch_current_price(exchange, ccxt_symbol)
                        current_price = current_price_cache[ccxt_symbol]
                    exit_price = current_price
                else:
                    exit_price = pick_first_price_at_or_after(hourly_points, target_ms)

                if exit_price is None:
                    hourly_missing_price_count[index] += 1
                    continue

                quantity = invest_usdt / entry_price
                pnl_usdt = (exit_price - entry_price) * quantity
                hourly_total_pnl[index] += pnl_usdt
                hourly_resolved_count[index] += 1

        for hour_offset in range(1, hour_count + 1):
            index = hour_offset - 1
            target_dt = fetched_dt + timedelta(hours=hour_offset)
            total_pnl = hourly_total_pnl[index]
            resolved_count = hourly_resolved_count[index]
            missing_price_count = hourly_missing_price_count[index]
            invalid_entry_count = hourly_invalid_entry_count[index]
            batch_total_investment = invest_usdt * batch_size
            batch_total_return_pct = (
                total_pnl / batch_total_investment * 100 if batch_total_investment > 0 else 0.0
            )

            status = "ok_realtime" if now < target_dt else "ok"
            valuation_dt = now if now < target_dt else target_dt
            if resolved_count == 0:
                if missing_price_count > 0:
                    status = "missing_price"
                elif invalid_entry_count > 0:
                    status = "invalid_entry_price"
            elif missing_price_count > 0 or invalid_entry_count > 0:
                status = "partial_missing_price"

            results.append(
                {
                    "fetched_at_utc": fetched_at,
                    "hour_offset": hour_offset,
                    "target_at_utc": target_dt.isoformat(),
                    "valuation_at_utc": valuation_dt.isoformat(),
                    "status": status,
                    "batch_size": batch_size,
                    "batch_resolved_count": resolved_count,
                    "batch_missing_price_count": missing_price_count,
                    "batch_invalid_entry_count": invalid_entry_count,
                    "batch_total_investment_usdt": round(batch_total_investment, 8),
                    "batch_total_pnl_usdt": round(total_pnl, 8),
                    "batch_total_return_pct": round(batch_total_return_pct, 6),
                }
            )

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


def save_hourly_results(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "fetched_at_utc",
        "hour_offset",
        "target_at_utc",
        "valuation_at_utc",
        "status",
        "batch_size",
        "batch_resolved_count",
        "batch_missing_price_count",
        "batch_invalid_entry_count",
        "batch_total_investment_usdt",
        "batch_total_pnl_usdt",
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
    parser.add_argument(
        "--hourly-output",
        type=Path,
        default=Path("data/top_gainers_24h_hourly_pnl.csv"),
        help="每个组合开仓后 24 小时内每小时盈亏输出路径",
    )
    args = parser.parse_args()

    source_rows = load_rows(args.input)
    for row in source_rows:
        fetched_at = row.get("fetched_at_utc", "").strip()
        if fetched_at:
            row["fetched_at_utc"] = normalize_fetched_at_utc(fetched_at)
    exchange = build_exchange()
    hourly_price_cache = build_hourly_price_cache(exchange, source_rows)
    result_rows = calc_24h_pnl(
        source_rows,
        invest_usdt=args.invest_usdt,
        exchange=exchange,
        hourly_price_cache=hourly_price_cache,
    )
    hourly_rows = calc_hourly_batch_pnl(
        source_rows,
        invest_usdt=args.invest_usdt,
        exchange=exchange,
        hourly_price_cache=hourly_price_cache,
    )
    save_results(result_rows, args.output)
    save_hourly_results(hourly_rows, args.hourly_output)

    print(f"已保存 {len(result_rows)} 条记录到: {args.output}", flush=True)
    print(f"已保存 {len(hourly_rows)} 条每小时组合盈亏到: {args.hourly_output}", flush=True)


if __name__ == "__main__":
    main()
