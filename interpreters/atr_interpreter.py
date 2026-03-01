"""ATR 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput


class ATRInterpreter(BaseInterpreter):
    """ATR 指标解释器"""
    
    indicator_name = "atr"

    def interpret(self, values: dict[str, float]) -> InterpreterOutput:
        atr = values.get('atr', 0)
        atr_percent = values.get('atr_percent', 0)
        stop_distance = values.get('stop_distance', atr * 1.5)
        stop_multiple = values.get('stop_multiple', 1.5)
        volatility = values.get('volatility', 'low')

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
