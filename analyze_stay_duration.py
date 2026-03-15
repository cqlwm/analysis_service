import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


def calculate_avg_stay_duration(csv_path: str) -> None:
    symbol_counter: Counter[str] = Counter()
    timestamps: list[datetime] = []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row["symbol"]
            symbol_counter[symbol] += 1
            ts = datetime.fromisoformat(row["fetched_at_utc"].replace("+00:00", ""))
            timestamps.append(ts)
    
    if not timestamps:
        print("No data found")
        return
    
    timestamps.sort()
    total_duration_hours = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
    
    total_stay = sum(symbol_counter.values())
    avg_stay_hours = total_stay / len(symbol_counter)
    
    stay_counts = list(symbol_counter.values())
    stay_counts.sort()
    n = len(stay_counts)
    if n % 2 == 0:
        median = (stay_counts[n // 2 - 1] + stay_counts[n // 2]) / 2
    else:
        median = stay_counts[n // 2]
    
    print(f"Data time range: {timestamps[0]} to {timestamps[-1]}")
    print(f"Total hours: {total_duration_hours:.1f}")
    print(f"Total records: {total_stay}")
    print(f"Unique symbols: {len(symbol_counter)}")
    print(f"Average stay duration: {avg_stay_hours:.2f} hours")
    print(f"Median stay duration: {median:.1f} hours")
    print()
    print("Top 10 symbols by appearances:")
    for symbol, count in symbol_counter.most_common(10):
        print(f"  {symbol}: {count} hours")


def calculate_median_max_change(csv_path: str) -> None:
    records: list[dict] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.fromisoformat(row["fetched_at_utc"].replace("+00:00", ""))
            records.append({
                "ts": ts,
                "symbol": row["symbol"],
                "change_percent": float(row["change_percent"]),
            })
    
    records.sort(key=lambda x: x["ts"])
    
    unique_hours = sorted(set(r["ts"] for r in records))
    hour_to_records: dict[datetime, list[dict]] = {h: [] for h in unique_hours}
    for r in records:
        hour_to_records[r["ts"]].append(r)
    
    symbol_appearances: dict[str, list[datetime]] = {}
    for ts, recs in hour_to_records.items():
        for r in recs:
            symbol = r["symbol"]
            if symbol not in symbol_appearances:
                symbol_appearances[symbol] = []
            symbol_appearances[symbol].append(ts)
    
    results: list[dict] = []
    for symbol, appearances in symbol_appearances.items():
        appearances.sort()
        
        max_changes: list[dict] = []
        segments: list[list[datetime]] = []
        current_segment = [appearances[0]]
        
        for i in range(1, len(appearances)):
            gap = (appearances[i] - appearances[i-1]).total_seconds() / 3600
            if gap <= 1.5:
                current_segment.append(appearances[i])
            else:
                segments.append(current_segment)
                current_segment = [appearances[i]]
        segments.append(current_segment)
        
        for segment in segments:
            entry_ts = segment[0]
            entry_change = None
            for r in records:
                if r["ts"] == entry_ts and r["symbol"] == symbol:
                    entry_change = r["change_percent"]
                    break
            
            max_change = entry_change if entry_change else 0.0
            for ts in segment:
                for r in records:
                    if r["ts"] == ts and r["symbol"] == symbol:
                        if r["change_percent"] > max_change:
                            max_change = r["change_percent"]
                        break
            
            max_changes.append({
                "entry_ts": entry_ts,
                "entry_change": entry_change if entry_change else 0.0,
                "max_change": max_change,
                "duration_hours": len(segment),
            })
        
        if max_changes:
            max_change_values = [mc["max_change"] for mc in max_changes]
            max_change_values_sorted = sorted(max_change_values)
            idx = len(max_change_values_sorted) // 2
            if len(max_change_values_sorted) % 2 == 0:
                median_max = (max_change_values_sorted[idx-1] + max_change_values_sorted[idx]) / 2
            else:
                median_max = max_change_values_sorted[idx]
            
            results.append({
                "symbol": symbol,
                "median_max_change": median_max,
                "max_changes": max_changes,
            })
    
    results.sort(key=lambda x: x["median_max_change"], reverse=True)
    
    print("\n=== Median Max Change per Token ===")
    print(f"Top 20 tokens by median max change:\n")
    for r in results[:20]:
        print(f"{r['symbol']}: {r['median_max_change']:.2f}%")
        for i, mc in enumerate(r["max_changes"]):
            print(f"  Entry {i+1}: {mc['entry_ts'].strftime('%m-%d %H:%M')} | entry: {mc['entry_change']:.2f}% | max: {mc['max_change']:.2f}% | {mc['duration_hours']}h")


if __name__ == "__main__":
    csv_path = Path(__file__).parent / "data" / "top_gainers.csv"
    calculate_avg_stay_duration(str(csv_path))
    calculate_median_max_change(str(csv_path))