"""ATR 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput
from indicators.atr import ATROutput


class ATRInterpreter(BaseInterpreter[ATROutput]):
    """ATR 指标解释器"""
    
    indicator_name = "atr"

    def interpret(self, indicator_summary: ATROutput) -> InterpreterOutput:
        atr = indicator_summary.atr
        atr_percent = indicator_summary.atr_percent
        stop_distance = indicator_summary.stop_distance
        stop_multiple = indicator_summary.stop_multiple
        volatility = indicator_summary.volatility

        summary = (
            f"风险层(ATR): atr={atr:.6f}, atr_pct={atr_percent:.2f}%, "
            f"stop_distance={stop_distance:.6f} (ATRx{stop_multiple})"
        )
        analysis = (
            f"ATR用于风险管理，当前波动级别={volatility}。"
            f"建议以ATRx{stop_multiple}设置动态止损距离({stop_distance:.6f})。"
            "本层不用于判断趋势方向。"
        )

        return {
            "analysis": analysis,
        }
