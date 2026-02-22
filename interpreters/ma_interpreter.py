"""均线指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput


class MAInterpreter(BaseInterpreter):
    """移动平均线指标解释器"""
    
    indicator_name = "ma"
    
    def interpret(self, values: dict[str, float]) -> InterpreterOutput:
        ma20 = values.get('ma20')
        ma50 = values.get('ma50')
        ma200 = values.get('ma200')
        close = values.get('close')
        
        # 均线排列判断
        ma_values = []
        if ma20 and ma20 == ma20:  # check NaN
            ma_values.append(('MA20', ma20))
        if ma50 and ma50 == ma50:
            ma_values.append(('MA50', ma50))
        if ma200 and ma200 == ma200:
            ma_values.append(('MA200', ma200))
        
        if len(ma_values) >= 2:
            # 检查排序
            sorted_asc = all(ma_values[i][1] <= ma_values[i+1][1] for i in range(len(ma_values)-1))
            sorted_desc = all(ma_values[i][1] >= ma_values[i+1][1] for i in range(len(ma_values)-1))
            
            if sorted_asc:
                arrangement = "多头排列(短均线在长均线上方)"
                trend = "上涨趋势"
                action = "顺势做多"
            elif sorted_desc:
                arrangement = "空头排列(短均线在长均线下方)"
                trend = "下跌趋势"
                action = "顺势做空"
            else:
                arrangement = "均线缠绕"
                trend = "震荡整理"
                action = "观望或区间操作"
        else:
            arrangement = "数据不足"
            trend = "不确定"
            action = "等待均线成型"
        
        # 价格与MA20关系
        price_vs_ma20 = ""
        if close and ma20 and ma20 == ma20:
            if close > ma20:
                price_vs_ma20 = f"价格在MA20({ma20:.4f})上方，看涨"
            else:
                price_vs_ma20 = f"价格在MA20({ma20:.4f})下方，看跌"
        
        ma20_str = f"{ma20:.4f}" if ma20 and ma20 == ma20 else "N/A"
        ma50_str = f"{ma50:.4f}" if ma50 and ma50 == ma50 else "N/A"
        ma200_str = f"{ma200:.4f}" if ma200 and ma200 == ma200 else "N/A"
        
        summary = f"MA20={ma20_str}, MA50={ma50_str}, MA200={ma200_str}，{arrangement}"
        analysis = f"均线显示{trend}。{arrangement}。{price_vs_ma20}。建议: {action}。均线是趋势指标，多头排列预示上涨，空头排列预示下跌。"
        
        return {
            "summary": summary,
            "analysis": analysis,
        }
