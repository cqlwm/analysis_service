"""布林带指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput


class BollingerInterpreter(BaseInterpreter):
    """布林带指标解释器"""
    
    indicator_name = "bollinger"

    def interpret(self, values: dict[str, float]) -> InterpreterOutput:
        position = values.get('position', values.get('bb_position', 50))
        zone = values.get('zone', 'middle')
        bandwidth_pct = values.get('bandwidth_pct', 0)
        squeeze_state = values.get('squeeze_state', 'normal')

        summary = (
            f"结构层(Bollinger): zone={zone}, position={position:.2f}%, "
            f"bandwidth={bandwidth_pct:.2f}%, squeeze={squeeze_state}"
        )
        analysis = (
            "布林带只回答当前位置与波动收缩状态。"
            f"当前位于{zone}，带宽{squeeze_state}。"
            "该层用于判断位置是否合适，不负责给方向。"
        )

        return {
            "summary": summary,
            "analysis": analysis,
        }
