"""AlphaTrend 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput
from indicators.alpha_trend import AlphaTrendOutput


class AlphaTrendInterpreter(BaseInterpreter):
    """AlphaTrend 指标解释器"""
    
    indicator_name = "alpha_trend"

    def interpret(self, values: AlphaTrendOutput | dict) -> InterpreterOutput:
        if isinstance(values, dict):
            at_mode = values.get("at_mode", "unknown")
            at_value = float(values.get("at_value", 0))
            deviation_pct = float(values.get("deviation_pct", 0))
            entry_dir = values.get("entry_direction", "none")
            bars_since_entry = int(values.get("bars_since_entry") or 0)
            exit_warning = bool(values.get("exit_warning", False))
            overall = values.get("overall", "weak")
        else:
            at_mode = values.at_mode
            at_value = values.at_value
            deviation_pct = values.deviation_pct
            entry_dir = values.entry_direction
            bars_since_entry = values.bars_since_entry or 0
            exit_warning = values.exit_warning
            overall = values.overall

        if entry_dir == "long":
            direction_desc = "多头边界"
        elif entry_dir == "short":
            direction_desc = "空头边界"
        else:
            direction_desc = "无有效边界"

        summary = (
            f"趋势层(AT): at={at_value:.4f}, mode={at_mode}, overall={overall}, "
            f"entry={entry_dir}, bars={bars_since_entry}, deviation={deviation_pct:+.2f}%"
        )

        warning_text = "触发退出预警" if exit_warning else "未触发退出预警"
        analysis = (
            f"Alpha Trend用于给出趋势边界，当前为{direction_desc}，{warning_text}。"
            f"价格相对AT偏离{deviation_pct:+.2f}%，用于判断是否离边界过远。"
            "本层用于定方向和边界，不单独作为最终开仓决策。"
        )

        return {
            "summary": summary,
            "analysis": analysis,
        }
