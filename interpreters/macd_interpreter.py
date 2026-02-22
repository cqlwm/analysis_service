"""MACD 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput


class MACDInterpreter(BaseInterpreter):
    """MACD 指标解释器"""
    
    indicator_name = "macd"
    
    def interpret(self, values: dict[str, float]) -> InterpreterOutput:
        macd = values.get('macd', 0)
        macd_signal = values.get('macd_signal', 0)
        macd_hist = values.get('macd_hist', 0)
        
        # 判断交叉
        if macd > macd_signal:
            cross = "金叉(多头信号)"
            trend = "上涨趋势"
            action = "关注做多机会"
        else:
            cross = "死叉(空头信号)"
            trend = "下跌趋势"
            action = "关注做空机会"
        
        # 判断动能
        if abs(macd_hist) > 0.5:
            momentum = "动能强劲"
        elif abs(macd_hist) > 0.1:
            momentum = "动能一般"
        else:
            momentum = "动能较弱"
        
        # 判断零轴
        if macd > 0:
            position = "零轴上方"
            bias = "偏多头"
        else:
            position = "零轴下方"
            bias = "偏空头"
        
        summary = f"MACD={macd:.4f}, Signal={macd_signal:.4f}, Hist={macd_hist:.4f}，{cross}，{position}，{momentum}"
        analysis = f"MACD指标显示{momentum}。当前{cross}，MACD线位于{position}({bias})，直方图{macd_hist:.4f}显示{'多方' if macd_hist > 0 else '空方'}力量较强。建议: {action}。"
        
        return {
            "summary": summary,
            "analysis": analysis,
        }
