"""成交量指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput


class VolumeInterpreter(BaseInterpreter):
    """成交量指标解释器"""
    
    indicator_name = "volume"
    
    def interpret(self, values: dict[str, float]) -> InterpreterOutput:
        volume = values.get('volume', 0)
        volume_ma = values.get('volume_ma', 0)
        volume_ratio = values.get('volume_ratio', 1)
        
        # 成交量判断
        if volume_ratio > 2:
            volume_desc = "大幅放量"
            implication = "趋势可能加速，或即将反转"
            action = "密切关注，配合其他指标判断"
        elif volume_ratio > 1.5:
            volume_desc = "放量"
            implication = "趋势得到量能确认"
            action = "顺势操作"
        elif volume_ratio > 1:
            volume_desc = "温和放量"
            implication = "趋势健康延续"
            action = "保持现有仓位"
        elif volume_ratio > 0.5:
            volume_desc = "缩量"
            implication = "趋势可能减弱，观望为主"
            action = "谨慎操作，等待确认"
        else:
            volume_desc = "大幅缩量"
            implication = "可能即将变盘"
            action = "保持观望，等待突破"
        
        summary = f"成交量={volume:.0f}，MA{values.get('ma_period', 20)}={volume_ma:.0f}，比率={volume_ratio:.2f}x，{volume_desc}"
        analysis = f"成交量指标显示{volume_desc}({volume_ratio:.2f}倍)。{implication}。建议: {action}。成交量是趋势的确认指标，放量上涨更可靠，缩量上涨需警惕。"
        
        return {
            "summary": summary,
            "analysis": analysis,
        }
