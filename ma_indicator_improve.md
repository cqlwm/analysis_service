我来系统性地梳理均线分析的维度，然后给出完整的代码实现。

## 分析维度设计

**1. 均线排列状态** — 多头/空头/混乱排列
**2. 均线间距** — 绝对值 & 相对价格的百分比
**3. 交叉状态** — 金叉/死叉，距上次交叉经历K线数
**4. 价格与均线关系** — 当前价在均线上/下方，偏离度
**5. 均线斜率** — 均线趋势方向（上升/下降/平坦）
**6. 均线粘合度** — 三线是否收敛（可能爆发信号）
**7. 支撑/压力** — 价格距最近均线的距离（是否在测试支撑）

---

```python
import pandas as pd
import numpy as np
import json

_high = 'high'
_low = 'low'
_open = 'open'
_close = 'close'
_volume = 'volume'

_ma20 = 'ma20'
_ma50 = 'ma50'
_ma200 = 'ma200'


def analyze_ma_indicators(df: pd.DataFrame, slope_period: int = 5) -> dict:
    """
    对包含均线的 K 线 DataFrame 进行多维度分析，输出 JSON 可序列化的摘要字典。

    Parameters
    ----------
    df           : 必须包含 close / ma20 / ma50 / ma200 列，按时间升序排列
    slope_period : 计算均线斜率所用的回看 K 线数（默认 5）
    """

    # ------------------------------------------------------------------ #
    #  基础校验
    # ------------------------------------------------------------------ #
    required = [_close, _ma20, _ma50, _ma200]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"DataFrame 缺少必要列: {col}")

    df = df.copy().reset_index(drop=True)
    close  = df[_close]
    ma20   = df[_ma20]
    ma50   = df[_ma50]
    ma200  = df[_ma200]

    last_close = float(close.iloc[-1])
    last_ma20  = float(ma20.iloc[-1])
    last_ma50  = float(ma50.iloc[-1])
    last_ma200 = float(ma200.iloc[-1])

    # ------------------------------------------------------------------ #
    #  辅助函数
    # ------------------------------------------------------------------ #
    def pct_diff(a: float, b: float) -> float:
        """a 相对 b 的百分比偏差，保留 4 位小数"""
        return round((a - b) / b * 100, 4) if b != 0 else None

    def slope_pct(series: pd.Series, n: int) -> float:
        """用最近 n 根 K 线的首尾值估算斜率（%/bar）"""
        if len(series) < n:
            return None
        start = float(series.iloc[-n])
        end   = float(series.iloc[-1])
        return round((end - start) / start * 100 / n, 5) if start != 0 else None

    def bars_since_cross(s_fast: pd.Series, s_slow: pd.Series) -> dict:
        """
        计算最近一次金叉/死叉距今的 K 线数，以及历史金叉死叉次数。
        金叉：fast 上穿 slow；死叉：fast 下穿 slow
        """
        diff  = s_fast - s_slow
        cross = diff.shift(1)

        golden = ((diff > 0) & (cross <= 0))  # 本根金叉
        death  = ((diff < 0) & (cross >= 0))  # 本根死叉

        last_golden_idx = golden[golden].index.max() if golden.any() else None
        last_death_idx  = death[death].index.max()  if death.any()  else None

        n = len(diff) - 1  # 最后一根的 index

        if last_golden_idx is not None and last_death_idx is not None:
            last_type    = "golden" if last_golden_idx > last_death_idx else "death"
            bars_since   = n - max(last_golden_idx, last_death_idx)
        elif last_golden_idx is not None:
            last_type, bars_since = "golden", n - last_golden_idx
        elif last_death_idx is not None:
            last_type, bars_since = "death",  n - last_death_idx
        else:
            last_type, bars_since = "none", None

        return {
            "last_cross_type"  : last_type,
            "bars_since_cross" : int(bars_since) if bars_since is not None else None,
            "golden_cross_count": int(golden.sum()),
            "death_cross_count" : int(death.sum()),
        }

    def squeeze_ratio(ma_list: list) -> float:
        """
        均线粘合度：所有均线极差 / 其均值，值越小越收敛。
        """
        spread = max(ma_list) - min(ma_list)
        mean   = sum(ma_list) / len(ma_list)
        return round(spread / mean * 100, 4) if mean != 0 else None

    def trend_label(s: float) -> str:
        if s is None: return "unknown"
        if s >  0.05: return "up"
        if s < -0.05: return "down"
        return "flat"

    # ------------------------------------------------------------------ #
    #  1. 均线排列
    # ------------------------------------------------------------------ #
    if last_ma20 > last_ma50 > last_ma200:
        alignment = "bullish"       # 多头排列
    elif last_ma20 < last_ma50 < last_ma200:
        alignment = "bearish"       # 空头排列
    else:
        alignment = "mixed"         # 混乱排列

    # ------------------------------------------------------------------ #
    #  2. 均线间距（绝对值 & 相对百分比）
    # ------------------------------------------------------------------ #
    spacing = {
        "ma20_vs_ma50": {
            "abs": round(last_ma20 - last_ma50, 6),
            "pct": pct_diff(last_ma20, last_ma50),
        },
        "ma20_vs_ma200": {
            "abs": round(last_ma20 - last_ma200, 6),
            "pct": pct_diff(last_ma20, last_ma200),
        },
        "ma50_vs_ma200": {
            "abs": round(last_ma50 - last_ma200, 6),
            "pct": pct_diff(last_ma50, last_ma200),
        },
    }

    # ------------------------------------------------------------------ #
    #  3. 交叉状态
    # ------------------------------------------------------------------ #
    cross_20_50  = bars_since_cross(ma20, ma50)
    cross_50_200 = bars_since_cross(ma50, ma200)
    cross_20_200 = bars_since_cross(ma20, ma200)

    # ------------------------------------------------------------------ #
    #  4. 价格与均线关系
    # ------------------------------------------------------------------ #
    price_vs_ma = {
        "close_vs_ma20" : {
            "above": last_close > last_ma20,
            "pct"  : pct_diff(last_close, last_ma20),
        },
        "close_vs_ma50" : {
            "above": last_close > last_ma50,
            "pct"  : pct_diff(last_close, last_ma50),
        },
        "close_vs_ma200": {
            "above": last_close > last_ma200,
            "pct"  : pct_diff(last_close, last_ma200),
        },
        # 离价格最近的均线（潜在支撑/压力）
        "nearest_ma": min(
            [("ma20", abs(last_close - last_ma20)),
             ("ma50", abs(last_close - last_ma50)),
             ("ma200",abs(last_close - last_ma200))],
            key=lambda x: x[1]
        )[0],
    }

    # ------------------------------------------------------------------ #
    #  5. 均线斜率（趋势方向）
    # ------------------------------------------------------------------ #
    s_ma20  = slope_pct(ma20,  slope_period)
    s_ma50  = slope_pct(ma50,  slope_period)
    s_ma200 = slope_pct(ma200, slope_period)

    slopes = {
        "ma20"  : {"slope_pct_per_bar": s_ma20,  "trend": trend_label(s_ma20)},
        "ma50"  : {"slope_pct_per_bar": s_ma50,  "trend": trend_label(s_ma50)},
        "ma200" : {"slope_pct_per_bar": s_ma200, "trend": trend_label(s_ma200)},
    }

    # ------------------------------------------------------------------ #
    #  6. 均线粘合度（收敛/发散）
    # ------------------------------------------------------------------ #
    current_squeeze = squeeze_ratio([last_ma20, last_ma50, last_ma200])

    # 用历史均值判断当前粘合度是否处于低位（收敛）
    hist_squeeze = df.apply(
        lambda row: squeeze_ratio([row[_ma20], row[_ma50], row[_ma200]]), axis=1
    ).dropna()
    squeeze_percentile = round(
        float((hist_squeeze < current_squeeze).mean() * 100), 2
    ) if len(hist_squeeze) > 0 else None

    squeeze = {
        "current_spread_pct"  : current_squeeze,
        "historical_percentile": squeeze_percentile,   # 越低越收敛
        "is_converging"        : squeeze_percentile is not None and squeeze_percentile < 20,
    }

    # ------------------------------------------------------------------ #
    #  7. 价格对均线的连续站上/站下 K 线数
    # ------------------------------------------------------------------ #
    def consecutive_above(price_s: pd.Series, ma_s: pd.Series) -> int:
        """最近连续站上(>0)或站下(<0)的 K 线数，正数=站上，负数=站下"""
        diff = (price_s - ma_s).iloc[::-1]  # 倒序
        above = diff.iloc[0] > 0
        count = 0
        for v in diff:
            if (v > 0) == above:
                count += 1
            else:
                break
        return count if above else -count

    consecutive = {
        "close_above_ma20" : consecutive_above(close, ma20),
        "close_above_ma50" : consecutive_above(close, ma50),
        "close_above_ma200": consecutive_above(close, ma200),
    }

    # ------------------------------------------------------------------ #
    #  汇总输出
    # ------------------------------------------------------------------ #
    summary = {
        "snapshot": {
            "close" : round(last_close, 6),
            "ma20"  : round(last_ma20,  6),
            "ma50"  : round(last_ma50,  6),
            "ma200" : round(last_ma200, 6),
        },
        "alignment"   : alignment,
        "spacing"     : spacing,
        "cross_20_50" : cross_20_50,
        "cross_50_200": cross_50_200,
        "cross_20_200": cross_20_200,
        "price_vs_ma" : price_vs_ma,
        "slopes"      : slopes,
        "squeeze"     : squeeze,
        "consecutive" : consecutive,
    }

    return summary


# ------------------------------------------------------------------ #
#  使用示例
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    # 构造示例数据
    np.random.seed(42)
    n = 300
    price = 100 + np.cumsum(np.random.randn(n) * 0.5)
    demo_df = pd.DataFrame({
        _close : price,
        _open  : price - np.random.rand(n) * 0.3,
        _high  : price + np.random.rand(n) * 0.5,
        _low   : price - np.random.rand(n) * 0.5,
        _volume: np.random.randint(1000, 5000, n),
    })
    demo_df[_ma20]  = demo_df[_close].rolling(20).mean()
    demo_df[_ma50]  = demo_df[_close].rolling(50).mean()
    demo_df[_ma200] = demo_df[_close].rolling(200).mean()
    demo_df.dropna(inplace=True)

    result = analyze_ma_indicators(demo_df)
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

---

## 输出结构说明

| 字段 | 含义 |
|---|---|
| `snapshot` | 最后一根 K 线的价格与三条均线值 |
| `alignment` | `bullish` 多头 / `bearish` 空头 / `mixed` 混乱排列 |
| `spacing` | 均线两两间距（绝对值 + 相对百分比） |
| `cross_20_50/50_200/20_200` | 各组均线的金叉/死叉类型、距今 K 线数、历史交叉次数 |
| `price_vs_ma` | 价格在各均线上/下方及偏离 %，以及最近均线（支撑/压力） |
| `slopes` | 各均线斜率（%/bar）及趋势方向 `up/down/flat` |
| `squeeze` | 均线粘合度、历史百分位（低=收敛=潜在爆发） |
| `consecutive` | 价格连续站上/站下某均线的 K 线数（负数=站下） |