"""成交量指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput
from indicators.volume import VolumeOutput


class VolumeInterpreter(BaseInterpreter[VolumeOutput]):
    """成交量指标解释器"""
    
    indicator_name = "volume"

    def interpret(self, indicator_summary: VolumeOutput) -> InterpreterOutput:
        volume = indicator_summary.volume
        volume_ma = indicator_summary.volume_ma
        ratio = indicator_summary.ratio
        obv = indicator_summary.obv
        obv_slope = indicator_summary.obv_slope
        obv_trend = indicator_summary.obv_trend

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
