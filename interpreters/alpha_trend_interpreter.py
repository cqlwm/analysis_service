"""AlphaTrend 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput


class AlphaTrendInterpreter(BaseInterpreter):
    """AlphaTrend 指标解释器"""
    
    indicator_name = "alpha_trend"
    
    def interpret(self, values: dict[str, float], signal: dict | None) -> InterpreterOutput:
        alpha_trend = values.get('alpha_trend', 0)
        atr = values.get('atr', 0)
        mfi = values.get('mfi', 50)
        signal_val = values.get('signal', 0)
        kline_count = values.get('kline_count_since_signal', 0)
        deviation = values.get('price_deviation_from_signal', 0)
        
        # 信号方向
        if signal_val == 1:
            direction = "多头信号"
            trend = "上涨趋势"
            action = "关注做多机会"
        elif signal_val == -1:
            direction = "空头信号"
            trend = "下跌趋势"
            action = "关注做空机会"
        else:
            direction = "无新信号"
            trend = "观望"
            action = "等待信号"
        
        # MFI 确认
        if mfi >= 50:
            mfi_confirm = "资金流入确认"
        else:
            mfi_confirm = "资金流出确认"
        
        # 偏离度判断
        if abs(deviation) > 5:
            deviation_desc = f"价格已偏离信号点{abs(deviation):.1f}%，{'注意回调' if deviation > 0 else '注意反弹'}"
        elif abs(deviation) > 2:
            deviation_desc = f"价格偏离信号点{abs(deviation):.1f}%，趋势延续中"
        else:
            deviation_desc = "价格接近信号点，趋势健康"
        
        summary = f"Alpha Trend={alpha_trend:.4f}，{direction}，MFI={mfi:.2f}，信号后{kline_count}根K线，偏离{deviation:+.1f}%"
        analysis = f"Alpha Trend指标显示{trend}。当前{direction}，MFI={mfi:.2f}({mfi_confirm})。{deviation_desc}。建议: {action}。Alpha Trend结合了ATR和MFI，是较创新的趋势追踪指标。"
        
        return {
            "summary": summary,
            "analysis": analysis,
        }
