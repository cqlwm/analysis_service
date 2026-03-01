"""MFI 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput
from indicators.mfi import MFIOutput


class MFIInterpreter(BaseInterpreter[MFIOutput]):
    """MFI 指标解释器"""
    
    indicator_name = "mfi"
    
    def interpret(self, indicator_summary: MFIOutput) -> InterpreterOutput:
        mfi = indicator_summary.mfi
        overbought = indicator_summary.overbought
        oversold = indicator_summary.oversold
        
        if mfi > overbought:
            zone = "超买区域"
            implication = "资金流入可能放缓，价格可能回落"
            action = "考虑减仓"
        elif mfi < oversold:
            zone = "超卖区域"
            implication = "资金流出可能反转，价格可能反弹"
            action = "关注买入机会"
        elif mfi >= 50:
            zone = "偏多区域"
            implication = "资金净流入，多头占优"
            action = "顺势做多"
        else:
            zone = "偏空区域"
            implication = "资金净流出，空头占优"
            action = "顺势做空"
        
        if mfi > 50:
            flow = "资金净流入"
        elif mfi < 50:
            flow = "资金净流出"
        else:
            flow = "资金平衡"
        
        summary = f"MFI={mfi:.2f}，位于{zone}，{flow}"
        analysis = f"MFI(资金流量指标)显示当前市场{zone}。{implication}。当前{mfi:.2f}表示{flow}。建议: {action}。MFI结合了价格和成交量，比RSI更可靠。"
        
        return {
            "analysis": analysis,
        }
