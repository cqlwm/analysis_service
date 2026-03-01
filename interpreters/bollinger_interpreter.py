"""布林带指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput
from indicators.bollinger import BollingerOutput


class BollingerInterpreter(BaseInterpreter[BollingerOutput]):
    """布林带指标解释器"""
    
    indicator_name = "bollinger"

    def interpret(self, indicator_summary: BollingerOutput) -> InterpreterOutput:
        position = indicator_summary.position
        zone = indicator_summary.zone
        bandwidth_pct = indicator_summary.bandwidth_pct
        squeeze_state = indicator_summary.squeeze_state

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
            "analysis": analysis,
        }
