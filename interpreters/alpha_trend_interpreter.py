"""AlphaTrend 指标解释器"""
from interpreters.base import BaseInterpreter, InterpreterOutput
from indicators.alpha_trend import AlphaTrendOutput


class AlphaTrendInterpreter(BaseInterpreter):
    """AlphaTrend 指标解释器"""
    
    indicator_name = "alpha_trend"

    def interpret(self, indicator_summary: AlphaTrendOutput) -> InterpreterOutput:
        at_mode = indicator_summary.at_mode
        at_value = indicator_summary.at_value
        deviation_pct = indicator_summary.deviation_pct
        entry_dir = indicator_summary.entry_direction
        bars_since_entry = indicator_summary.bars_since_entry or 0
        entry_price = indicator_summary.entry_price
        entry_deviation_pct = indicator_summary.entry_deviation_pct or 0
        exit_warning = indicator_summary.exit_warning
        overall = indicator_summary.overall
        high_since_signal = indicator_summary.high_since_signal
        low_since_signal = indicator_summary.low_since_signal
        high_since_kline_count = indicator_summary.high_since_kline_count
        low_since_kline_count = indicator_summary.low_since_kline_count
        max_drawdown = indicator_summary.max_drawdown
        key_alpha_values = indicator_summary.key_alpha_values or []
        stop_loss_price = indicator_summary.stop_loss_price
        
        if entry_dir == "long":
            direction_desc = "多头边界"
        elif entry_dir == "short":
            direction_desc = "空头边界"
        else:
            direction_desc = "无有效边界"

        if at_mode == "rising":
            mode_desc = "上升中"
        elif at_mode == "falling":
            mode_desc = "下降中"
        elif at_mode == "flat":
            mode_desc = "走平"
        else:
            mode_desc = "未知"

        if overall == "bullish":
            overall_desc = "多头趋势"
        elif overall == "bearish":
            overall_desc = "空头趋势"
        elif overall == "neutral":
            overall_desc = "中性整理"
        else:
            overall_desc = "趋势不明"

        analysis_parts = [f"【趋势层】Alpha Trend 当前值为 {at_value}，处于{mode_desc}状态，整体判定为{overall_desc}。"]

        if entry_dir != "none" and entry_price:
            analysis_parts.append(f"【信号时效】最近信号为{entry_dir}，出现在此刻{bars_since_entry}根K线之前。")
            analysis_parts.append(f"入场价 {entry_price}，当前价格{"高于" if entry_deviation_pct > 0 else "低于"}入场价 {abs(entry_deviation_pct):.2f}%。")

            if high_since_signal and high_since_kline_count:
                analysis_parts.append(f"信号后最高价 {high_since_signal}（信号发生后，第{high_since_kline_count}根K线）。")
            if low_since_signal and low_since_kline_count:
                analysis_parts.append(f"信号后最低价 {low_since_signal}（信号发生后，第{low_since_kline_count}根K线）。")
            if max_drawdown:
                analysis_parts.append(
                    f"最大价格回撤 {max_drawdown*100:.2f}%。"
                    f"注释：信号触发后，价格趋势向信号相反方向移动的过程称为回撤。"
                    f"其中，看涨信号下，价格达到阶段性最高价后回调至低点的过程为回撤；"
                    f"看跌信号下，价格达到阶段性最低价后反弹至高点的过程也为回撤。"
                )

            if exit_warning:
                analysis_parts.append("【风险提示】触发退出预警，价格已穿越Alpha Trend边界，需密切关注是否需要离场。")
            else:
                analysis_parts.append("【信号状态】未触发退出预警，当前趋势仍在延续。")

            if stop_loss_price:
                analysis_parts.append(f"建议止损位：{stop_loss_price}。")
        else:
            analysis_parts.append("【信号状态】当前无有效交易信号，等待下一个信号产生。")

        if key_alpha_values:
            key_vals_str = ", ".join([f"{v}" for v in key_alpha_values])
            analysis_parts.append(f"【关键价位】Alpha Trend 关键值：{key_vals_str}。")

        analysis_parts.append(
            f"【偏离警示】价格相对AT偏离{deviation_pct:+.2f}%，偏离过大时需警惕回调/反弹风险。"
            "本层用于定方向和边界，不单独作为最终开仓决策，需结合其他指标确认。"
        )

        return {
            "analysis": "\n".join(analysis_parts)
        }
