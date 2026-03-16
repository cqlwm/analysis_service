import csv
import argparse
from datetime import datetime
from pathlib import Path

import pymysql

from config.database import get_db_config


def parse_fetched_at(dt_str: str) -> datetime:
    """解析 ISO 格式时间并截断到整点。"""
    dt = datetime.fromisoformat(dt_str.replace("+00:00", ""))
    return dt.replace(minute=0, second=0, microsecond=0)


def migrate_csv(csv_path: Path) -> int:
    config = get_db_config()
    conn = pymysql.connect(**config.dict)
    count = 0
    batch_size = 100
    batch: list[tuple] = []
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO top_gainers (
                    fetched_at_utc, rank, symbol, base, quote,
                    change_percent, last_price, open_price, high_price, low_price,
                    volume, quote_volume, trade_count, updated_at_ms
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
            """
            with csv_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fetched_at = parse_fetched_at(row["fetched_at_utc"])
                    batch.append((
                        fetched_at,
                        int(row["rank"]),
                        row["symbol"],
                        row["base"],
                        row["quote"],
                        float(row["change_percent"]),
                        float(row["last_price"]),
                        float(row["open_price"]),
                        float(row["high_price"]),
                        float(row["low_price"]),
                        float(row["volume"]),
                        float(row["quote_volume"]),
                        int(row["trade_count"]),
                        int(row["updated_at_ms"]),
                    ))
                    if len(batch) >= batch_size:
                        cursor.executemany(sql, batch)
                        count += len(batch)
                        batch = []
                if batch:
                    cursor.executemany(sql, batch)
                    count += len(batch)
        conn.commit()
        print(f"成功导入 {count} 条记录")
    finally:
        conn.close()
    return count


def main():
    parser = argparse.ArgumentParser(description="将 CSV 数据迁移到 MariaDB")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/top_gainers.csv"),
        help="CSV 文件路径",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"文件不存在: {args.csv}")
        return

    migrate_csv(args.csv)


if __name__ == "__main__":
    main()
