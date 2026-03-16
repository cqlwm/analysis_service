import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def analyze_24h_pnl(csv_path: str) -> None:
    records: list[dict] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({
                "symbol": row["symbol"],
                "entry_price": float(row["entry_price"]),
                "exit_price": float(row["exit_price"]),
                "invest_usdt": float(row["invest_usdt"]),
                "pnl_usdt": float(row["pnl_usdt"]),
                "pnl_pct": float(row["pnl_pct"]),
                "batch_size": int(row["batch_size"]),
                "batch_total_pnl_usdt": float(row["batch_total_pnl_usdt"]),
                "batch_total_investment_usdt": float(row["batch_total_investment_usdt"]),
                "batch_total_return_pct": float(row["batch_total_return_pct"]),
                "fetched_at_utc": row["fetched_at_utc"],
            })

    if not records:
        print("No data found")
        return

    pnl_pcts = [r["pnl_pct"] for r in records]
    pnl_pcts_sorted = sorted(pnl_pcts)

    winning_trades = [p for p in pnl_pcts if p > 0]
    losing_trades = [p for p in pnl_pcts if p < 0]

    def median(values: list[float]) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n % 2 == 0:
            return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
        return sorted_vals[n // 2]

    def mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def std(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        m = mean(values)
        variance = sum((x - m) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def percentile(values: list[float], p: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = (len(sorted_vals) - 1) * p / 100
        lower = int(idx)
        upper = lower + 1
        if upper >= len(sorted_vals):
            return sorted_vals[-1]
        weight = idx - lower
        return sorted_vals[lower] * (1 - weight) + sorted_vals[upper] * weight

    print("=" * 60)
    print("24h PnL Analysis")
    print("=" * 60)

    print("\n--- 基础统计 ---")
    print(f"总交易笔数: {len(records)}")
    print(f"盈利交易: {len(winning_trades)} ({len(winning_trades) / len(records) * 100:.1f}%)")
    print(f"亏损交易: {len(losing_trades)} ({len(losing_trades) / len(records) * 100:.1f}%)")
    print(f"胜率: {len(winning_trades) / len(records) * 100:.1f}%")

    print("\n--- pnl_pct 统计 ---")
    print(f"均值: {mean(pnl_pcts):.2f}%")
    print(f"中位数: {median(pnl_pcts):.2f}%")
    print(f"标准差: {std(pnl_pcts):.2f}%")
    print(f"最大涨幅: {max(pnl_pcts):.2f}%")
    print(f"最大跌幅: {min(pnl_pcts):.2f}%")

    print("\n--- 分位数 ---")
    print(f"5%:  {percentile(pnl_pcts, 5):.2f}%")
    print(f"25%: {percentile(pnl_pcts, 25):.2f}%")
    print(f"50%: {percentile(pnl_pcts, 50):.2f}%")
    print(f"75%: {percentile(pnl_pcts, 75):.2f}%")
    print(f"95%: {percentile(pnl_pcts, 95):.2f}%")

    print("\n--- 盈利交易统计 ---")
    print(f"数量: {len(winning_trades)}")
    print(f"最大盈利: {max(winning_trades):.2f}%")
    print(f"最小盈利: {min(winning_trades):.2f}%")
    print(f"中位数盈利: {median(winning_trades):.2f}%")
    print(f"盈利 > 5%: {len([p for p in winning_trades if p > 5]) / len(records) * 100:.1f}%")
    print(f"盈利 > 10%: {len([p for p in winning_trades if p > 10]) / len(records) * 100:.1f}%")
    print(f"盈利 > 20%: {len([p for p in winning_trades if p > 20]) / len(records) * 100:.1f}%")

    print("\n--- 亏损交易统计 ---")
    print(f"数量: {len(losing_trades)}")
    print(f"最大亏损: {min(losing_trades):.2f}%")
    print(f"最小亏损: {max(losing_trades):.2f}%")
    print(f"中位数亏损: {median(losing_trades):.2f}%")

    batches: dict[int, list[dict]] = defaultdict(list)
    for r in records:
        batches[r["batch_size"]].append(r)

    print("\n--- Batch 维度 ---")
    for batch_size in sorted(batches.keys()):
        batch_records = batches[batch_size]
        batch_pnl = [r["batch_total_pnl_usdt"] for r in batch_records]
        batch_return = [r["batch_total_return_pct"] for r in batch_records]
        batch_wins = len([r for r in batch_records if r["pnl_pct"] > 0])

        print(f"\nBatch size: {batch_size}")
        print(f"  样本数: {len(batch_records)}")
        print(f"  总投入: {batch_records[0]['batch_total_investment_usdt']:.0f} USDT")
        print(f"  总盈亏: {batch_records[0]['batch_total_pnl_usdt']:.2f} USDT")
        print(f"  总回报率: {batch_records[0]['batch_total_return_pct']:.2f}%")
        print(f"  胜率: {batch_wins / len(batch_records) * 100:.1f}%")

    symbol_pnl: dict[str, list[float]] = defaultdict(list)
    for r in records:
        symbol_pnl[r["symbol"]].append(r["pnl_pct"])

    print("\n--- Symbol 维度 ---")
    symbol_stats = []
    for symbol, pnl_list in symbol_pnl.items():
        symbol_stats.append({
            "symbol": symbol,
            "count": len(pnl_list),
            "avg_pnl_pct": mean(pnl_list),
            "max_pnl_pct": max(pnl_list),
            "min_pnl_pct": min(pnl_list),
        })

    symbol_stats.sort(key=lambda x: x["avg_pnl_pct"], reverse=True)

    print("\nTop 10 平均收益最高的 token:")
    for s in symbol_stats[:10]:
        print(f"  {s['symbol']}: avg={s['avg_pnl_pct']:.2f}%, max={s['max_pnl_pct']:.2f}%, min={s['min_pnl_pct']:.2f}%, count={s['count']}")

    print("\n出现次数最多的 token:")
    symbol_stats_by_count = sorted(symbol_stats, key=lambda x: x["count"], reverse=True)
    for s in symbol_stats_by_count[:10]:
        print(f"  {s['symbol']}: count={s['count']}, avg={s['avg_pnl_pct']:.2f}%")


if __name__ == "__main__":
    csv_path = Path(__file__).parent / "data" / "top_gainers_24h_pnl.csv"
    analyze_24h_pnl(str(csv_path))
