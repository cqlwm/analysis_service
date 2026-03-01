"""成交量指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput


class VolumeInterpreter(BaseInterpreter):
    """成交量指标解释器"""
    
    indicator_name = "volume"

    def interpret(self, values: dict[str, float]) -> InterpreterOutput:
        volume = values.get('volume', 0)
        volume_ma = values.get('volume_ma', 0)
        ratio = values.get('ratio', values.get('volume_ratio', 1))
        obv = values.get('obv', 0)
        obv_slope = values.get('obv_slope', 0)
        obv_trend = values.get('obv_trend', 'flat')

        summary = (
            f"资金层(Volume+OBV): volume={volume:.0f}, volume_ma={volume_ma:.0f}, "
            f"ratio={ratio:.2f}x, obv={obv:.0f}, obv_trend={obv_trend}"
        )
        analysis = (
            "资金层用于确认参与度与资金方向。"
            f"当前量比={ratio:.2f}x，OBV斜率={obv_slope:+.4f}%({obv_trend})。"
            "该层用于确认，不单独给趋势方向。"
        )

        return {
            "analysis": analysis,
        }
