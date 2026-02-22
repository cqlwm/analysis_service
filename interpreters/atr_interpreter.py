"""ATR 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput


class ATRInterpreter(BaseInterpreter):
    """ATR 指标解释器"""
    
    indicator_name = "atr"
    
    def interpret(self, values: dict[str, float]) -> InterpreterOutput:
        atr = values.get('atr', 0)
        atr_percent = values.get('atr_percent', 0)
        
        # 波动率判断
        if atr_percent > 5:
            volatility = "高波动"
            risk_level = "高风险"
            action = "适当缩小仓位，降低杠杆"
        elif atr_percent > 2:
            volatility = "中等波动"
            risk_level = "中等风险"
            action = "正常仓位管理"
        else:
            volatility = "低波动"
            risk_level = "低风险"
            action = "等待突破，谨慎操作"
        
        # 止盈止损建议
        stop_loss_suggest = atr * 1.5
        take_profit_suggest = atr * 3
        
        summary = f"ATR={atr:.6f} ({atr_percent:.2f}%)，{volatility}"
        analysis = f"ATR显示当前市场波动率为{atr_percent:.2f}%，属于{volatility}。{risk_level}级别。建议: {action}。可根据ATR设置止损，建议止损幅度: {stop_loss_suggest:.4f}，止盈目标: {take_profit_suggest:.4f}。"
        
        return {
            "summary": summary,
            "analysis": analysis,
        }
