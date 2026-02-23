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


## 均线指标摘要字段的分析意义与实际应用

---

### 1. `alignment` — 均线排列

**分析意义**

均线排列反映的是不同时间维度趋势的一致性。MA20代表短期趋势，MA50代表中期趋势，MA200代表长期趋势。当三者方向一致时，说明多空力量在各个时间维度上形成合力。

**实际应用**

`bullish`（多头排列，MA20 > MA50 > MA200）是趋势交易者最青睐的进场前提，此时回调到MA20或MA50附近往往是较优的做多时机。`bearish`（空头排列）则相反，反弹至均线附近是做空机会。`mixed`（混乱排列）说明市场处于震荡或趋势转换期，此时均线策略的胜率会显著下降，应降低仓位或等待排列明朗。

---

### 2. `spacing` — 均线间距

**分析意义**

均线间距的百分比（`pct`）比绝对值更有参考价值，它衡量的是趋势的"成熟度"和"张力"。间距越大说明趋势延续时间越长、力度越强，但同时也意味着均线回归的拉力在积累。

**实际应用**

以`ma20_vs_ma200.pct`为例，如果该值超过历史均值的2倍标准差，往往预示短期过热，价格存在回调压力。反之，如果三组间距都极小（结合`squeeze`字段），则可能是大行情启动前的蓄力阶段。在实际使用中，可以将`spacing.pct`纳入仓位管理模型：间距过大时适当缩减追涨仓位，回调收窄后再加仓。

---

### 3. `cross_20_50` / `cross_50_200` / `cross_20_200` — 交叉状态

**分析意义**

这三组交叉信号的"权重"是递增的。MA20与MA50的交叉（20/50）灵敏但噪音多，适合中短线；MA50与MA200的交叉（50/200）是经典的"黄金交叉/死亡交叉"，是机构级别的趋势确认信号，假信号较少但滞后明显；MA20与MA200的交叉介于两者之间。

**`bars_since_cross` 的实际意义**

这是容易被忽视但非常重要的字段。交叉刚发生时（bars_since_cross较小），信号新鲜，趋势加速的概率较高，是动量策略的进场窗口。随着bars_since_cross增大，说明趋势已经持续了一段时间，此时追入的性价比下降，需要结合spacing判断是否过度延伸。

**`golden_cross_count` / `death_cross_count` 的实际意义**

在给定的历史数据窗口内，如果金叉和死叉次数都很多，说明该品种均线交叉频繁，均线策略在此品种上的有效性存疑（震荡市特征）。如果金叉次数明显多于死叉，且目前处于金叉状态，则是趋势性品种的正面信号。

---

### 4. `price_vs_ma` — 价格与均线关系

**分析意义**

价格相对均线的位置和偏离幅度（`pct`）是判断短期超买超卖的直接指标，本质上是一种均值回归的度量。

**`nearest_ma` 的实际意义**

距离价格最近的均线是当前最直接的动态支撑或压力位。当价格在均线上方时，最近均线是支撑；当价格在均线下方时，最近均线是压力。这个字段能帮助自动识别当前最需要关注的均线层级，而不用手动判断。

**`close_vs_ma200.pct` 的特殊意义**

MA200的偏离度在宏观择时上有重要参考价值。历史数据表明，当价格偏离MA200超过某个阈值（如+50%或-30%）时，往往处于阶段性极端区域，适合做反向预期管理。

---

### 5. `slopes` — 均线斜率

**分析意义**

斜率比均线位置更能反映动量的当下状态。一个常见的误区是：价格在均线上方就认为是多头，但如果MA20的斜率已经由正转负（trend从up变flat或down），说明短期动量在衰减，趋势可能即将转变，此时仍然做多的风险在上升。

**实际应用**

三条均线斜率的组合是趋势健康度的综合体检。最健康的多头状态是三条均线斜率都为正且MA20斜率 > MA50斜率 > MA200斜率，说明短期动量强于中期强于长期，趋势正在加速。如果出现MA20斜率转负但MA50和MA200仍为正，通常是正常回调，可以考虑逢低做多。如果MA50斜率也转负，则需要警惕趋势转换。

---

### 6. `squeeze` — 均线粘合度

**分析意义**

这是整个摘要里预测性最强的字段之一。均线粘合意味着短中长期趋势的"分歧收敛"——市场参与者在不同时间维度上的判断趋于一致，能量在蓄积。历史上绝大多数大行情的启动前，均线都会经历一段粘合期。

**`historical_percentile` 的核心价值**

这个字段将当前粘合度放到历史分布中衡量，解决了"多紧才算紧"的问题。percentile低于20%说明当前粘合程度处于历史上最收敛的20%区间，是值得重点关注的潜在爆发前兆。

**实际应用**

squeeze本身不指示方向，需要结合价格突破和成交量来判断方向。实践中可以用`is_converging: true`作为"待观察"标记，触发更细粒度的价格行为分析，而不是直接作为交易信号。

---

### 7. `consecutive` — 价格连续站上/站下 K 线数

**分析意义**

这个字段衡量的是价格与均线关系的稳定性。连续站上某均线的K线数越多，说明该均线作为支撑的有效性越强，空头突破的难度越大。

**正负值的含义**

正数表示连续站上，绝对值越大，均线支撑越稳固；负数表示连续站下，绝对值越大，均线压力越顽固。

**实际应用**

当`close_above_ma200`从较大的负数（如-30）突然转为正数，是非常强烈的趋势转折信号，因为它意味着价格长期受压后首次站上长期均线。反之亦然。对于日内或短线策略，`close_above_ma20`的连续值可以用作持仓信心指标：在多头趋势中，如果这个值突然从正转负（价格跌破MA20），可以作为减仓或止损的参考触发条件。

---

### 字段组合使用示例

在实际系统中，这些字段的价值在于组合判断，而非单独使用。以下是几个典型的组合逻辑：

**强趋势确认**：`alignment == "bullish"` + `cross_50_200.last_cross_type == "golden"` + `slopes.ma200.trend == "up"` + `consecutive.close_above_ma200 > 0`，四个条件同时满足时，是介入多头趋势的高置信度场景。

**潜在爆发扫描**：`squeeze.is_converging == true` + `alignment != "mixed"` + `cross_20_50.bars_since_cross < 10`，用于筛选蓄力完成且方向初步明确的品种进入观察池。

**过热预警**：`spacing.ma20_vs_ma200.pct` 超过历史90%分位 + `slopes.ma20.slope_pct_per_bar`明显大于`slopes.ma50`，说明短期涨幅透支，应控制追涨仓位。

**趋势衰竭识别**：`alignment == "bullish"` 但 `slopes.ma20.trend == "down"` + `consecutive.close_above_ma20`由正转负，说明多头排列仍在但短期动量已经衰竭，是减仓而非加仓的时机。