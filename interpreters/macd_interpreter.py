"""MACD 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput
from indicators.macd import MACDOutput


class MACDInterpreter(BaseInterpreter[MACDOutput]):
    """MACD 指标解释器"""
    
    indicator_name = "macd"

    def interpret(self, indicator_summary: MACDOutput) -> InterpreterOutput:
        macd = indicator_summary.macd
        signal_line = indicator_summary.signal_line
        hist = indicator_summary.hist
        zero_axis = indicator_summary.zero_axis
        hist_momentum = indicator_summary.hist_momentum
        support = indicator_summary.momentum_support
        divergence = indicator_summary.divergence_warning
        bullish_divergence = indicator_summary.bullish_divergence
        bearish_divergence = indicator_summary.bearish_divergence

        if bearish_divergence:
            divergence_type = '顶背离'
        elif bullish_divergence:
            divergence_type = '底背离'
        elif divergence:
            divergence_type = '背离'
        else:
            divergence_type = '无'

        summary = (
            f"动量层(MACD): macd={macd:.4f}, signal={signal_line:.4f}, hist={hist:.4f}, "
            f"zero_axis={zero_axis}, momentum={hist_momentum}, support={support}, divergence={divergence_type}"
        )
        analysis = (
            "MACD用于验证动量是否支持当前方向。"
            f"当前零轴位置={zero_axis}，柱体变化={hist_momentum}。"
            f"背离预警={'是' if divergence else '否'}（{divergence_type}）。"
            "本层不作为独立开仓信号。"
        )

        return {
            "analysis": analysis,
        }
