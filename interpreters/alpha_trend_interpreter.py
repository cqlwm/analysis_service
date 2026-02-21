"""AlphaTrend 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput
from indicators.alpha_trend import AlphaTrendOutput


class AlphaTrendInterpreter(BaseInterpreter):
    """AlphaTrend 指标解释器"""
    
    indicator_name = "alpha_trend"
    
    def interpret(self, output: AlphaTrendOutput, signal: dict | None = None) -> InterpreterOutput:
        at_mode = output.at_mode
        entry_dir = output.entry_direction
        bars_since = output.bars_since_entry or 0
        deviation = output.entry_deviation_pct or 0
        exit_warning = output.exit_warning
        price_above_at = output.price_above_at
        
        if entry_dir == "long":
            direction_desc = "多头趋势"
            action = "关注做多机会"
        elif entry_dir == "short":
            direction_desc = "空头趋势"
            action = "关注做空机会"
        else:
            direction_desc = "无趋势信号"
            action = "等待信号"
        
        if at_mode == "rising":
            mode_desc = "AT上升中，动态支撑有效"
        elif at_mode == "falling":
            mode_desc = "AT下降中，动态压力有效"
        elif at_mode == "flat":
            mode_desc = "AT走平，震荡过滤模式"
        else:
            mode_desc = "AT状态未知"
        
        if abs(deviation) > 5:
            deviation_desc = f"价格已偏离入场点{abs(deviation):.1f}%，{'注意回调' if deviation > 0 else '注意反弹'}"
        elif abs(deviation) > 2:
            deviation_desc = f"价格偏离入场点{abs(deviation):.1f}%，趋势延续中"
        else:
            deviation_desc = "价格接近入场点，趋势健康"
        
        exit_info = "⚠️ 退出预警激活" if exit_warning else "无退出预警"
        
        summary = (
            f"AT {at_mode}，{direction_desc}，"
            f"持续{bars_since}根K线，偏离入场价{deviation:+.1f}%，"
            f"{exit_info}"
        )
        
        analysis = (
            f"Alpha Trend指标分析：{mode_desc}。"
            f"当前{direction_desc}，已持续{bars_since}根K线。"
            f"{deviation_desc}。"
            f"{exit_info}。"
            f"建议: {action}。"
            f"Alpha Trend结合了ATR和MFI，是较创新的趋势追踪指标。"
        )
        
        return {
            "summary": summary,
            "analysis": analysis,
        }
