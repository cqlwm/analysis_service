## 设计要点说明

**背离检测的核心逻辑**是找价格波峰/波谷与MACD柱波峰/波谷之间的"方向不一致"。代码用 `_find_pivots` 先找出所有摆动高点和低点，再配对比较。允许±N根的位置误差是因为价格波峰和MACD波峰在时间上不会完全对齐。

**`momentum_direction` 的四种状态**比简单的多/空更精确：

| 状态 | 含义 | 对 LLM 的价值 |
|---|---|---|
| `bullish` | 零轴上 + 正柱 | 动量最强，趋势延续概率高 |
| `weakening_bull` | 零轴上 + 负柱 | 多头动量在衰减，配合AT退出预警使用 |
| `weakening_bear` | 零轴下 + 正柱 | 空头动量在衰减，可能是底部反转前兆 |
| `bearish` | 零轴下 + 负柱 | 动量最弱，趋势延续概率高 |

**`strength_percentile`** 解决了"柱状图数值大小没有参照"的问题，LLM拿到90%这个数字就能直接判断当前动量处于历史强区，而不需要自己理解绝对数值的含义。

**`consecutive_bars`** 与 Alpha Trend 的 `bars_since_entry` 配合使用时很有价值：如果AT入场已经20根K线，但MACD柱连续方向只有3根，说明动量和趋势之间出现了分歧，是减仓而非加仓的信号。

```python

"""MACD 指标 - 动量强度 & 背离预警"""
import numpy as np
import pandas as pd
from pandas import DataFrame
import talib as ta

from indicators.base import BaseIndicator, IndicatorOutput, SignalDirection


# 列名常量
_HIGH    = 'high'
_LOW     = 'low'
_CLOSE   = 'close'

_MACD        = 'macd'
_MACD_SIGNAL = 'macd_signal'
_MACD_HIST   = 'macd_hist'


class MACDIndicator(BaseIndicator):
    """
    MACD 指标

    职责：
      - 动量方向：当前动量偏多还是偏空
      - 动量强度：柱状图的绝对值及其变化趋势（扩张/收缩）
      - 背离预警：价格与MACD柱状图之间的顶背离/底背离

    不负责：
      - 独立的交易信号（入场/出场由 Alpha Trend 决定）
      - 趋势方向判断（由 MA 三线负责）
    """

    name         = "macd"
    display_name = "MACD"

    # MACD 参数
    fast_period   = 12
    slow_period   = 26
    signal_period = 9

    # 背离检测参数
    divergence_lookback = 30   # 向前查找波峰/波谷的最大范围
    divergence_pivot_n  = 5    # 判断波峰/波谷所需的左右各N根K线

    def calculate(self, df: DataFrame) -> DataFrame:
        df = df.copy()

        close_values = df[_CLOSE].values.astype(np.float64)

        macd, signal, hist = ta.MACD(
            close_values,
            fastperiod=self.fast_period,
            slowperiod=self.slow_period,
            signalperiod=self.signal_period,
        )

        df[_MACD]        = macd
        df[_MACD_SIGNAL] = signal
        df[_MACD_HIST]   = hist

        return df

    # ──────────────────────────────────────────────────────────
    #  辅助：波峰 / 波谷检测
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _find_pivots(series: pd.Series, n: int) -> tuple[list[int], list[int]]:
        """
        在 series 中查找波峰和波谷的索引列表。
        波峰：左右各 n 根都小于该点
        波谷：左右各 n 根都大于该点
        返回 (peak_indices, trough_indices)
        """
        peaks   = []
        troughs = []
        values  = series.values

        for i in range(n, len(values) - n):
            window = values[i - n: i + n + 1]
            if np.isnan(window).any():
                continue
            center = values[i]
            if center == np.max(window) and center > values[i - 1] and center > values[i + 1]:
                peaks.append(i)
            if center == np.min(window) and center < values[i - 1] and center < values[i + 1]:
                troughs.append(i)

        return peaks, troughs

    # ──────────────────────────────────────────────────────────
    #  辅助：背离检测
    # ──────────────────────────────────────────────────────────
    def _detect_divergence(
        self,
        df: pd.DataFrame,
        idx: int,
    ) -> dict:
        """
        在 [idx - divergence_lookback, idx] 窗口内检测背离。

        顶背离（bearish divergence）：
          价格创出更高的波峰，但 MACD 柱状图的对应波峰更低
          → 上涨动量衰竭，趋势可能反转向下

        底背离（bullish divergence）：
          价格创出更低的波谷，但 MACD 柱状图的对应波谷更高
          → 下跌动量衰竭，趋势可能反转向上

        返回结构：
        {
            "bearish": bool,   # 是否存在顶背离
            "bullish": bool,   # 是否存在底背离
            "detail": str,     # 简要描述
        }
        """
        start = max(0, idx - self.divergence_lookback)
        window_df     = df.iloc[start: idx + 1].copy()
        window_close  = window_df[_CLOSE].reset_index(drop=True)
        window_hist   = window_df[_MACD_HIST].reset_index(drop=True)

        n = self.divergence_pivot_n

        price_peaks,   price_troughs  = self._find_pivots(window_close, n)
        hist_peaks,    hist_troughs   = self._find_pivots(window_hist,  n)

        bearish = False
        bullish = False
        details = []

        # ── 顶背离：取最近两个价格波峰，对比对应 MACD 柱波峰 ──
        if len(price_peaks) >= 2 and len(hist_peaks) >= 2:
            # 最近两个价格波峰
            pp1, pp2 = price_peaks[-2], price_peaks[-1]
            price_high1 = float(window_close.iloc[pp1])
            price_high2 = float(window_close.iloc[pp2])

            # 在对应位置附近找最近的 MACD 波峰（允许±n根误差）
            def nearest_hist_peak(target_i):
                candidates = [p for p in hist_peaks if abs(p - target_i) <= n]
                if not candidates:
                    return None
                return min(candidates, key=lambda p: abs(p - target_i))

            hp1 = nearest_hist_peak(pp1)
            hp2 = nearest_hist_peak(pp2)

            if hp1 is not None and hp2 is not None:
                hist_high1 = float(window_hist.iloc[hp1])
                hist_high2 = float(window_hist.iloc[hp2])
                # 价格高点抬高，MACD 高点降低 → 顶背离
                if price_high2 > price_high1 and hist_high2 < hist_high1:
                    bearish = True
                    details.append(
                        f"顶背离：价格 {price_high1:.4f}→{price_high2:.4f}（↑），"
                        f"MACD柱 {hist_high1:.4f}→{hist_high2:.4f}（↓）"
                    )

        # ── 底背离：取最近两个价格波谷，对比对应 MACD 柱波谷 ──
        if len(price_troughs) >= 2 and len(hist_troughs) >= 2:
            pt1, pt2 = price_troughs[-2], price_troughs[-1]
            price_low1 = float(window_close.iloc[pt1])
            price_low2 = float(window_close.iloc[pt2])

            def nearest_hist_trough(target_i):
                candidates = [t for t in hist_troughs if abs(t - target_i) <= n]
                if not candidates:
                    return None
                return min(candidates, key=lambda t: abs(t - target_i))

            ht1 = nearest_hist_trough(pt1)
            ht2 = nearest_hist_trough(pt2)

            if ht1 is not None and ht2 is not None:
                hist_low1 = float(window_hist.iloc[ht1])
                hist_low2 = float(window_hist.iloc[ht2])
                # 价格低点降低，MACD 低点抬高 → 底背离
                if price_low2 < price_low1 and hist_low2 > hist_low1:
                    bullish = True
                    details.append(
                        f"底背离：价格 {price_low1:.4f}→{price_low2:.4f}（↓），"
                        f"MACD柱 {hist_low1:.4f}→{hist_low2:.4f}（↑）"
                    )

        return {
            "bearish": bearish,
            "bullish": bullish,
            "detail" : "；".join(details) if details else "无背离",
        }

    # ──────────────────────────────────────────────────────────
    #  summarize
    # ──────────────────────────────────────────────────────────
    def summarize(self, df: DataFrame, latest_idx: int = -1) -> IndicatorOutput:
        df  = df.copy().reset_index(drop=True)
        idx = len(df) + latest_idx if latest_idx < 0 else latest_idx

        current   = df.iloc[idx]
        macd_val  = float(current[_MACD])
        sig_val   = float(current[_MACD_SIGNAL])
        hist_val  = float(current[_MACD_HIST])

        hist_series = df[_MACD_HIST].iloc[:idx + 1]

        # ── 1. 零轴位置 ──────────────────────────────────────
        # MACD线在零轴上方：整体处于多头动量区
        # MACD线在零轴下方：整体处于空头动量区
        # 零轴上方的金叉/死叉比零轴下方的信号更可靠
        above_zero = macd_val > 0

        # ── 2. MACD线与信号线的关系 ──────────────────────────
        # macd > signal → 柱状图为正 → 多头动量占优
        # macd < signal → 柱状图为负 → 空头动量占优
        hist_positive = hist_val > 0

        # ── 3. 柱状图变化趋势（扩张 / 收缩）────────────────
        # 柱状图绝对值扩大：动量加速，趋势延续概率高
        # 柱状图绝对值收缩：动量衰竭，需要警惕趋势减弱
        lookback = min(3, idx)
        hist_window = hist_series.dropna().iloc[-lookback - 1:]

        if len(hist_window) >= 2:
            prev_hist = float(hist_window.iloc[-2])
            curr_hist = float(hist_window.iloc[-1])

            # 用绝对值比较扩张/收缩
            if abs(curr_hist) > abs(prev_hist):
                hist_momentum = "expanding"   # 动量扩张
            elif abs(curr_hist) < abs(prev_hist):
                hist_momentum = "contracting" # 动量收缩
            else:
                hist_momentum = "flat"
        else:
            hist_momentum = "unknown"

        # ── 4. 柱状图连续同向根数 ────────────────────────────
        # 连续多根同向扩张 → 趋势动量稳定
        # 方向突然改变 → 动量转折信号
        hist_vals = hist_series.dropna().values
        consecutive = 0
        if len(hist_vals) >= 1:
            direction = np.sign(hist_vals[-1])
            for v in reversed(hist_vals):
                if np.sign(v) == direction:
                    consecutive += 1
                else:
                    break

        # ── 5. 历史强度百分位 ────────────────────────────────
        # 当前柱状图绝对值在历史中的位置
        # 高百分位 → 动量处于历史强区，可能过热
        # 低百分位 → 动量较弱，趋势动力不足
        hist_abs = hist_series.dropna().abs()
        if len(hist_abs) > 0:
            strength_percentile = round(
                float((hist_abs < abs(hist_val)).mean() * 100), 1
            )
        else:
            strength_percentile = None

        # ── 6. 背离检测 ──────────────────────────────────────
        divergence = self._detect_divergence(df, idx)

        # ── 7. 综合动量方向 ──────────────────────────────────
        if above_zero and hist_positive:
            momentum_direction = "bullish"      # 零轴上方且多头柱：强多头动量
        elif not above_zero and not hist_positive:
            momentum_direction = "bearish"      # 零轴下方且空头柱：强空头动量
        elif above_zero and not hist_positive:
            momentum_direction = "weakening_bull"  # 零轴上方但空头柱：多头动量减弱
        else:
            momentum_direction = "weakening_bear"  # 零轴下方但多头柱：空头动量减弱

        # 背离会覆盖方向的置信度
        divergence_warning = divergence["bearish"] or divergence["bullish"]

        # ── 组装摘要 ─────────────────────────────────────────
        return {
            "name"        : self.name,
            "display_name": self.display_name,

            # MACD 原始值（供其他模块参考）
            "values": {
                "macd"   : round(macd_val, 6),
                "signal" : round(sig_val,  6),
                "hist"   : round(hist_val, 6),
            },

            # 动量状态（核心）
            "momentum": {
                "direction"          : momentum_direction,
                # bullish / bearish / weakening_bull / weakening_bear
                "above_zero"         : above_zero,
                # True = 多头动量区，False = 空头动量区
                "hist_momentum"      : hist_momentum,
                # expanding = 加速，contracting = 衰减，flat = 平稳
                "consecutive_bars"   : consecutive,
                # 当前方向连续了多少根K线
                "strength_percentile": strength_percentile,
                # 当前动量强度在历史中的百分位（越高越强）
            },

            # 背离预警（逆势信号）
            "divergence": {
                "warning": divergence_warning,   # 是否存在任何背离
                "bearish": divergence["bearish"], # 顶背离：上涨动量衰竭预警
                "bullish": divergence["bullish"], # 底背离：下跌动量衰竭预警
                "detail" : divergence["detail"],
            },

            "signal": {
                "direction"  : "long" if momentum_direction in ("bullish", "weakening_bear")
                               else "short" if momentum_direction in ("bearish", "weakening_bull")
                               else "neutral",
                "description": (
                    f"动量{momentum_direction}，"
                    f"{'零轴上方' if above_zero else '零轴下方'}，"
                    f"柱状图{hist_momentum}，"
                    f"连续{consecutive}根，"
                    f"强度百分位{strength_percentile}%，"
                    f"{'⚠️ 背离预警：' + divergence['detail'] if divergence_warning else '无背离'}"
                ),
            },
        }

    def get_column_names(self) -> list[str]:
        return [_MACD, _MACD_SIGNAL, _MACD_HIST]

```