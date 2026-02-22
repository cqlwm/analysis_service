"""布林带指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput


class BollingerInterpreter(BaseInterpreter):
    """布林带指标解释器"""
    
    indicator_name = "bollinger"
    
    def interpret(self, values: dict[str, float]) -> InterpreterOutput:
        bb_upper = values.get('bb_upper', 0)
        bb_middle = values.get('bb_middle', 0)
        bb_lower = values.get('bb_lower', 0)
        bb_position = values.get('bb_position', 50)
        
        # 判断位置
        if bb_position >= 90:
            position_desc = "触及上轨"
            implication = "价格极度超买，可能回落"
            action = "考虑减仓或做空"
        elif bb_position <= 10:
            position_desc = "触及下轨"
            implication = "价格极度超卖，可能反弹"
            action = "关注买入机会"
        elif bb_position > 80:
            position_desc = "接近上轨"
            implication = "价格偏强，注意回调风险"
            action = "谨慎追高"
        elif bb_position < 20:
            position_desc = "接近下轨"
            implication = "价格偏弱，注意反弹机会"
            action = "关注支撑位"
        else:
            position_desc = "中轨附近"
            implication = "价格处于震荡区间中部"
            action = "观望为主"
        
        # 计算带宽
        bandwidth = bb_upper - bb_lower
        bandwidth_pct = (bandwidth / bb_middle * 100) if bb_middle != 0 else 0
        
        if bandwidth_pct > 10:
            volatility = "高波动"
        elif bandwidth_pct > 5:
            volatility = "中等波动"
        else:
            volatility = "低波动"
        
        summary = f"布林带: 上轨={bb_upper:.4f} 中轨={bb_middle:.4f} 下轨={bb_lower:.4f}，位置={bb_position:.0f}%，{position_desc}，{volatility}"
        analysis = f"布林带显示价格在{position_desc}({bb_position:.0f}%)。{implication}。当前波动率: {bandwidth_pct:.2f}({volatility})。建议: {action}。布林带收窄通常预示即将突破。"
        
        return {
            "summary": summary,
            "analysis": analysis,
        }
