"""MACD 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput


class MACDInterpreter(BaseInterpreter):
    """MACD 指标解释器"""
    
    indicator_name = "macd"

    def interpret(self, values: dict[str, float]) -> InterpreterOutput:
        macd = values.get('macd', 0)
        signal_line = values.get('signal_line', values.get('macd_signal', 0))
        hist = values.get('hist', values.get('macd_hist', 0))
        zero_axis = values.get('zero_axis', 'crossing')
        hist_momentum = values.get('hist_momentum', 'flat')
        support = values.get('momentum_support', 'neutral')
        divergence = bool(values.get('divergence_warning', False))
        bullish_divergence = bool(values.get('bullish_divergence', False))
        bearish_divergence = bool(values.get('bearish_divergence', False))

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
            "summary": summary,
            "analysis": analysis,
        }
