"""AlphaTrend 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput
from indicators.alpha_trend import AlphaTrendOutput


class AlphaTrendInterpreter(BaseInterpreter):
    """AlphaTrend 指标解释器"""
    
    indicator_name = "alpha_trend"
    
    def interpret(self, values: AlphaTrendOutput) -> InterpreterOutput:
        # AT 状态
        at_mode = values.at_mode
        at_value = values.at_value
        at_change_pct = values.at_change_pct
        
        # 价格相对位置
        price_above_at = values.price_above_at
        deviation_pct = values.deviation_pct
        
        # 入场信息
        entry_dir = values.entry_direction
        bars_since_entry = values.bars_since_entry or 0
        entry_deviation_pct = values.entry_deviation_pct or 0
        
        # 退出信息
        exit_warning = values.exit_warning
        bars_since_exit = values.bars_since_exit
        exit_tests = values.exit_tests
        
        # 整体判断
        overall = values.overall
        
        # 入场方向描述
        if entry_dir == "long":
            direction_desc = "多头趋势"
            action = "关注做多机会"
            position_desc = "价格位于AT上方" if price_above_at else "价格位于AT下方"
        elif entry_dir == "short":
            direction_desc = "空头趋势"
            action = "关注做空机会"
            position_desc = "价格位于AT下方" if not price_above_at else "价格位于AT上方"
        else:
            direction_desc = "无趋势信号"
            action = "等待信号"
            position_desc = "价格与AT关系未知"
        
        # AT 模式描述
        if at_mode == "rising":
            mode_desc = "AT上升中，动态支撑有效"
            trend_strength = "趋势偏多"
        elif at_mode == "falling":
            mode_desc = "AT下降中，动态压力有效"
            trend_strength = "趋势偏空"
        elif at_mode == "flat":
            mode_desc = "AT走平，震荡过滤模式"
            trend_strength = "趋势不明，保持观望"
        else:
            mode_desc = "AT状态未知"
            trend_strength = "无法判断"
        
        # AT 变化幅度
        if at_change_pct is not None:
            if abs(at_change_pct) < 0.01:
                change_desc = "AT基本持平"
            elif at_change_pct > 0:
                change_desc = f"AT近{values.bars_since_entry or 0}根K线上涨{at_change_pct:.2f}%"
            else:
                change_desc = f"AT近{values.bars_since_entry or 0}根K线下跌{abs(at_change_pct):.2f}%"
        else:
            change_desc = "AT变化数据不足"
        
        # 偏离程度
        if abs(deviation_pct) > 5:
            deviation_desc = f"价格已偏离AT {abs(deviation_pct):.1f}%，{'注意回调风险' if deviation_pct > 0 else '注意反弹机会'}"
        elif abs(deviation_pct) > 2:
            deviation_desc = f"价格偏离AT {abs(deviation_pct):.1f}%，趋势延续中"
        else:
            deviation_desc = "价格接近AT，趋势健康"
        
        # 退出预警
        if exit_warning:
            exit_info = f"⚠️ 退出预警激活（已持续{bars_since_exit}根K线）"
        else:
            exit_info = "无退出预警"
        
        # 退出测试分析
        exit_tests_desc = ""
        if exit_tests:
            recent_tests = exit_tests[-3:]  # 只显示最近3次
            test_details = []
            for test in recent_tests:
                test_deviation = (test.close_price - test.at_val) / test.at_val * 100
                test_details.append(f"AT={test.at_val:.4f}, 价格={test.close_price:.4f}({test_deviation:+.1f}%)")
            exit_tests_desc = f"退出测试: {'; '.join(test_details)}"
        
        # 整体判断
        overall_map = {
            "bullish": "整体偏多",
            "bearish": "整体偏空",
            "neutral": "整体中性",
            "weak": "趋势偏弱",
        }
        overall_desc = overall_map.get(overall, "无法判断")
        
        # Summary
        summary = (
            f"AT {at_value:.4f} ({at_mode})，{direction_desc}，"
            f"已持续{bars_since_entry}根K线，当前偏差{deviation_pct:+.1f}%，"
            f"{overall_desc}，{exit_info}"
        )
        
        # Analysis
        analysis = (
            f"Alpha Trend指标分析：{mode_desc}。"
            f"{change_desc}，{position_desc}。"
            f"当前{direction_desc}，已持续{bars_since_entry}根K线。"
            f"{deviation_desc}。"
            f"入场价格偏差: {entry_deviation_pct:+.1f}%。"
            f"{exit_info}。"
            f"{exit_tests_desc}。"
            f"整体判断: {overall_desc}。"
            f"建议: {action}。"
            f"Alpha Trend结合了ATR和MFI，是较创新的趋势追踪指标。"
        )
        
        return {
            "summary": summary,
            "analysis": analysis,
        }
