"""Prompt构建层 - 将指标数据转化为自然语言描述"""
from dataclasses import asdict, is_dataclass
from typing import Any

from pandas import DataFrame

from interpreters import InterpreterRegistry
from strategies import CompositeStrategy, StrategySummary


class PromptBuilder:
    """Prompt构建器 - 输出符合五层指标系统的提示词"""

    def __init__(self, strategy: CompositeStrategy | None = None):
        self.strategy = strategy or CompositeStrategy()

    def build_analysis_prompt(
        self,
        symbol: str,
        timeframe: str,
        data_range: str,
        df: DataFrame,
    ) -> str:
        df = self.strategy.calculate_all(df)
        summary = self.strategy.generate_summary(df)
        return self._build_prompt_content(symbol, timeframe, data_range, summary)

    def _build_prompt_content(
        self,
        symbol: str,
        timeframe: str,
        data_range: str,
        summary: StrategySummary,
    ) -> str:
        header = (
            f"📈 交易对: {symbol}\n"
            f"⏰ 时间周期: {timeframe}\n"
            f"📅 数据范围: {data_range}\n"
            f"💵 最新价格: {summary['latest_price']}\n"
        )

        indicators_section = self._format_indicators(summary["indicators"])
        score_section = self._format_score_matrix(summary)

        footer = """
## 📝 任务要求（严格执行）
请按以下顺序分析，不要跳步：
1. 趋势层：先判断大方向（MA三线+Alpha Trend）
2. 结构层：判断当前价格位置（布林带位置与带宽）
3. 动量层：判断MACD动量是否支持，若背离需重点提示
4. 资金层：判断Volume+OBV是否确认参与度
5. 风险层：结合ATR给出止损距离和仓位风险

请特别遵守：
- MACD与ATR不能作为独立入场信号
- 优先参考评分矩阵与总分，不要只凭单一指标下结论

输出要求（markdown）：
- 趋势判断
- 关键支撑/阻力位
- 入场条件与失效条件
- 风险控制（止损、仓位）
- 最终交易建议（高置信度/降仓位或等待/不入场）
"""
        return "\n".join([header, indicators_section, score_section, footer])

    def _extract_values(self, indicator: Any) -> tuple[str, str, dict[str, Any], Any]:
        if is_dataclass(indicator):
            values = asdict(indicator)
            name = values.get("name", "unknown")
            display_name = values.get("display_name", name)
            signal = values.get("signal") or values.get("signal_obj")
            return str(name), str(display_name), values, signal

        if hasattr(indicator, "__dict__"):
            values = dict(indicator.__dict__)
            name = values.get("name", "unknown")
            display_name = values.get("display_name", name)
            signal = values.get("signal") or values.get("signal_obj")
            return str(name), str(display_name), values, signal

        if isinstance(indicator, dict):
            name = indicator.get("name", "unknown")
            display_name = indicator.get("display_name", name)
            signal = indicator.get("signal")
            return str(name), str(display_name), indicator, signal

        return "unknown", "unknown", {}, None

    def _format_indicators(self, indicators: list[Any]) -> str:
        lines = ["## 📊 技术指标分析"]

        if not indicators:
            lines.append("暂无指标数据")
        else:

            for indicator in indicators:
                name, display_name, values, _signal = self._extract_values(indicator)
                interpreter = InterpreterRegistry.get(name) or InterpreterRegistry.get("_default")
                interpreted = interpreter.interpret(values) if interpreter else {
                    "summary": "无数据",
                    "analysis": "无分析",
                }

                lines.append(f"### {display_name}")
                lines.append(f"- {interpreted['summary']}")
                lines.append(f"- {interpreted['analysis']}")

        return "\n".join(lines)

    @staticmethod
    def _decision_text(decision: str) -> str:
        mapping = {
            "high_confidence": "高置信度入场",
            "reduced_or_wait": "降仓位入场或等待",
            "no_entry": "不入场",
        }
        return mapping.get(decision, decision)

    def _format_score_matrix(self, summary: StrategySummary) -> str:
        score_matrix = summary.get("score_matrix", {})
        total_score = summary.get("total_score", 0)
        decision = self._decision_text(summary.get("decision", "no_entry"))

        lines = [
            "## 🎯 五层评分矩阵",
            "| 层级 | 分值 | 依据 |",
            "|------|------|------|",
        ]

        layer_names = {
            "trend": "趋势层",
            "structure": "结构层",
            "momentum": "动量层",
            "flow": "资金层",
            "volatility": "波动率层",
        }

        for key in ["trend", "structure", "momentum", "flow", "volatility"]:
            layer = score_matrix.get(key, {"score": 0, "reason": "无数据"})
            score = layer.get("score", 0)
            reason = layer.get("reason", "无数据")
            lines.append(f"| {layer_names[key]} | {score:+d} | {reason} |")

        lines.append("")
        lines.append(f"- **总分**: {int(total_score):+d}")
        lines.append(f"- **决策**: {decision}")
        lines.append("- **阈值规则**: 总分>=3 高置信度；1~2 降仓位或等待；<=0 不入场")

        return "\n".join(lines)

    def get_latest_values(self, df: DataFrame) -> dict[str, float]:
        df = self.strategy.calculate_all(df)
        column_names = self.strategy.get_all_column_names()
        latest = df.iloc[-1]
        return {col: float(latest[col]) for col in column_names if col in latest}
