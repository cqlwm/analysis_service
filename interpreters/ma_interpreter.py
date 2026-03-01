"""均线指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput


class MAInterpreter(BaseInterpreter):
    """移动平均线指标解释器"""
    
    indicator_name = "ma"

    def interpret(self, values: dict[str, float]) -> InterpreterOutput:
        mas = values.get('mas', {}) if isinstance(values.get('mas'), dict) else {}
        ma20 = mas.get('ma20', values.get('ma20'))
        ma50 = mas.get('ma50', values.get('ma50'))
        ma200 = mas.get('ma200', values.get('ma200'))
        alignment = values.get('alignment', 'mixed')
        price_vs_ma = values.get('price_vs_ma', 'unknown')

        if alignment == 'bullish':
            trend = '多头趋势'
        elif alignment == 'bearish':
            trend = '空头趋势'
        else:
            trend = '趋势不清晰'

        summary = (
            f"趋势层(MA): alignment={alignment}, "
            f"MA20={ma20}, MA50={ma50}, MA200={ma200}"
        )
        analysis = (
            f"MA三线用于判断方向与强度，当前为{trend}。"
            f"价格相对MA20状态: {price_vs_ma}。"
            "本层只给方向，不单独给入场点。"
        )

        return {
            "analysis": analysis,
        }
