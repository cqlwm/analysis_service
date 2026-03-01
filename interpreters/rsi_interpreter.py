"""RSI 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput
from indicators.rsi import RSIOutput


class RSIInterpreter(BaseInterpreter[RSIOutput]):
    """RSI 指标解释器 - 将RSI数据转换为自然语言"""
    
    indicator_name = "rsi"
    
    def interpret(self, indicator_summary: RSIOutput) -> InterpreterOutput:
        rsi = indicator_summary.rsi
        period = indicator_summary.period
        overbought = indicator_summary.overbought
        oversold = indicator_summary.oversold
        
        if rsi > overbought:
            zone = "超买区域"
            implication = "价格可能过热，存在回调风险"
            action = "谨慎追高，考虑减仓或止盈"
        elif rsi < oversold:
            zone = "超卖区域"
            implication = "价格可能被低估，存在反弹机会"
            action = "关注买入机会，但需等待确认信号"
        else:
            zone = "中性区域"
            implication = "多空双方力量相对均衡"
            action = "保持观望，等待趋势明确"
        
        summary = f"RSI({period})当前值为{rsi:.2f}，位于{zone}({oversold}-{overbought})，{implication}"
        analysis = f"RSI指标显示当前市场{zone}。{implication}。建议: {action}。技术面上，RSI大于70表示超买，小于30表示超卖。"
        
        return {
            "analysis": analysis,
        }
