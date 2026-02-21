"""Prompt构建层 - 将指标数据转化为自然语言描述"""
from pandas import DataFrame

from strategies import CompositeStrategy, StrategySummary
from interpreters import InterpreterRegistry


class PromptBuilder:
    """
    Prompt构建器 - 将指标数据转化为LLM可理解的自然语言描述
    
    设计原则:
    - 指标计算与prompt构建解耦
    - 解释器独立，将结构化数据转换为自然语言
    - 支持自定义模板
    - 生成结构化的prompt便于LLM理解
    """
    
    def __init__(self, strategy: CompositeStrategy | None = None):
        self.strategy = strategy or CompositeStrategy()
    
    def build_analysis_prompt(
        self,
        symbol: str,
        timeframe: str,
        data_range: str,
        df: DataFrame,
    ) -> str:
        """
        构建分析Prompt
        
        Args:
            symbol: 交易对，如 "BTC/USDT"
            timeframe: 时间周期，如 "1h"
            data_range: 数据范围，如 "2024-01-01 ~ 2024-01-31"
            df: OHLCV数据
            
        Returns:
            完整的分析Prompt
        """
        # 计算指标
        df = self.strategy.calculate_all(df)
        summary = self.strategy.generate_summary(df)
        
        # 构建prompt
        prompt = self._build_prompt_content(symbol, timeframe, data_range, summary)
        return prompt
    
    def _build_prompt_content(
        self,
        symbol: str,
        timeframe: str,
        data_range: str,
        summary: StrategySummary,
    ) -> str:
        """构建prompt内容"""
        # 头部信息
        header = f"""📈 交易对: {symbol}
⏰ 时间周期: {timeframe}
📅 数据范围: {data_range}

---"""
        
        # 技术指标部分（使用解释器生成自然语言）
        indicators_section = self._format_indicators(summary['indicators'])
        
        # 底部任务说明
        footer = """
## 📝 任务要求
请根据以上技术指标生成专业的行情分析报告，包括：
1. 当前趋势判断
2. 关键支撑/阻力位
3. 入场理由
4. 风险提示
5. 交易建议

请使用markdown格式输出。
"""
        return header + indicators_section + footer
    
    def _format_indicators(self, indicators: list[dict]) -> str:
        """格式化指标为表格（使用解释器生成自然语言）"""
        if not indicators:
            return "\n暂无指标数据\n"
        
        lines = ["\n## 📊 技术指标分析\n"]
        
        for ind in indicators:
            display_name = ind.get('display_name', ind['name'])
            values = ind['values']
            signal = ind.get('signal')
            indicator_name = ind['name']
            
            # 使用解释器生成自然语言描述
            interpreter = InterpreterRegistry.get(indicator_name)
            if interpreter:
                interpreted = interpreter.interpret(values, signal)
                summary = interpreted['summary']
                analysis = interpreted['analysis']
            else:
                # 使用默认解释器
                default_interpreter = InterpreterRegistry.get('_default')
                if default_interpreter:
                    interpreted = default_interpreter.interpret(values, signal)
                    summary = interpreted['summary']
                    analysis = interpreted['analysis']
                else:
                    summary = "无数据"
                    analysis = "无分析"
            
            # 指标名称
            lines.append(f"### {display_name}")
            
            # 解释器生成的摘要
            lines.append(f"- {summary}")
            
            # 解释器生成的分析
            lines.append(f"- {analysis}")
            
            # 信号方向
            if signal and signal.get('direction'):
                lines.append(f"- **信号方向**: {signal['direction']}")
            
            # 关键值表格
            if values:
                table = self._build_value_table(values)
                lines.append(table)
            
            lines.append("")  # 空行分隔
        
        return "\n".join(lines)
    
    def _build_value_table(self, values: dict) -> str:
        """将字典转换为Markdown表格"""
        if not values:
            return ""
        
        lines = ["| 指标 | 数值 |", "|--------|--------|"]
        for key, value in values.items():
            if isinstance(value, float):
                if abs(value) < 1:
                    lines.append(f"| {key} | {value:.6f} |")
                else:
                    lines.append(f"| {key} | {value:.2f} |")
            else:
                lines.append(f"| {key} | {value} |")
        
        return "\n".join(lines)
    
    def get_latest_values(self, df: DataFrame) -> dict[str, float]:
        """
        获取所有指标的最新值
        
        用于下游消费（如提取交易信号）
        """
        df = self.strategy.calculate_all(df)
        column_names = self.strategy.get_all_column_names()
        
        latest = df.iloc[-1]
        return {col: float(latest[col]) for col in column_names if col in latest}
