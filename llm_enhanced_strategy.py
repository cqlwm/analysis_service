"""
LLM增强的Alpha Trend策略
使用 OpenAI GPT API
"""

import json
import os
from typing import Any, List
from openai.types.chat import ChatCompletionMessageParam
from datetime import datetime
from dataclasses import dataclass, asdict
import pandas as pd
from pandas import DataFrame

from alpha_trend_strategy import AlphaTrendStrategy


@dataclass
class MarketContext:
    """市场上下文数据结构"""
    # 价格数据
    current_price: float
    price_change_24h: float
    price_change_7d: float
    
    # 技术指标
    alpha_trend_value: float
    alpha_trend_direction: str  # "up" / "down"
    rsi: float
    rsi_status: str  # "oversold" / "overbought" / "neutral"
    macd_signal: str  # "bullish" / "bearish" / "neutral"
    volume_ratio: float
    
    # 支撑阻力
    support_levels: List[float]
    resistance_levels: List[float]
    
    # 其他
    volatility: str  # "high" / "medium" / "low"
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LLMAnalysis:
    """LLM分析结果"""
    market_phase: str  # "uptrend" / "downtrend" / "sideways" / "reversal"
    trend_strength: str  # "strong" / "medium" / "weak"
    sentiment: str  # "greedy" / "fearful" / "neutral"
    key_observation: str
    confidence: float  # 0.0-1.0
    reasoning: str
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NewsFlash:
    """交易快讯"""
    title: str
    content: str
    style: str  # "professional" / "beginner" / "social"
    timestamp: str
    signal_type: str  # "BUY" / "SELL" / "HOLD"
    
    def to_dict(self) -> dict:
        return asdict(self)


class LLMProvider:
    """OpenAI LLM提供商"""
    
    def __init__(self):
        self._setup_client()
    
    def _setup_client(self):
        """初始化OpenAI客户端"""
        try:
            import openai
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_API_BASE_URL")
            if not api_key:
                print("⚠️  请设置环境变量: OPENAI_API_KEY")
                self.client = None
            else:
                self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
                self.model = "deepseek-ai/DeepSeek-V3.2"
        except ImportError:
            print("⚠️  OpenAI未安装，请运行: pip install openai")
            self.client = None
    
    def generate(self, messages: list[dict[str, str]], max_tokens: int = 2000) -> str:
        """调用LLM生成内容"""
        if not self.client:
            return self._fallback_response()
        
        # 转换消息格式以符合OpenAI类型要求
        chat_messages: list[ChatCompletionMessageParam] = messages  # type: ignore
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=chat_messages,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"❌ LLM调用失败: {e}")
            return self._fallback_response()
    
    def _fallback_response(self) -> str:
        """LLM不可用时的备用响应"""
        return json.dumps({
            "market_phase": "unknown",
            "trend_strength": "medium",
            "sentiment": "neutral",
            "key_observation": "LLM分析暂时不可用，请以技术指标为准",
            "confidence": 0.5
        })


class PromptTemplates:
    """提示词模板库"""
    
    @staticmethod
    def market_analysis(context: MarketContext) -> str:
        """市场分析提示词"""
        return f"""你是一位经验丰富的量化交易分析师。请根据以下技术指标数据，分析当前市场状态。

【价格数据】
- 当前价格: {context.current_price:.2f}
- 24小时涨跌: {context.price_change_24h:+.2f}%
- 7日涨跌: {context.price_change_7d:+.2f}%

【技术指标】
- Alpha Trend: {context.alpha_trend_value:.2f} (方向: {context.alpha_trend_direction})
- RSI: {context.rsi:.2f} (状态: {context.rsi_status})
- MACD: {context.macd_signal}
- 成交量比率: {context.volume_ratio:.2f}x

【价格位置】
- 支撑位: {', '.join(map(str, context.support_levels))}
- 阻力位: {', '.join(map(str, context.resistance_levels))}
- 波动率: {context.volatility}

请严格按照以下JSON格式返回分析结果（不要包含任何markdown格式或额外文字）:
{{
  "market_phase": "uptrend/downtrend/sideways/reversal之一",
  "trend_strength": "strong/medium/weak之一",
  "sentiment": "greedy/fearful/neutral之一",
  "key_observation": "一句话总结关键观察，50字以内",
  "confidence": 0.0到1.0之间的数字,
  "reasoning": "详细推理过程，100字以内"
}}

注意：只返回JSON，不要有任何其他内容。"""
    
    @staticmethod
    def generate_flash(
        signal: dict, 
        context: MarketContext,
        llm_analysis: LLMAnalysis,
        style: str = "professional"
    ) -> str:
        """快讯生成提示词"""
        
        if style == "professional":
            return f"""请根据以下交易信号，生成一条专业的交易快讯（200-300字）：

【信号信息】
类型: {signal['signal']}
强度: {signal.get('strength', 0):.1f}%
入场价格: {signal.get('entry_price', 0):.2f}
止损价格: {signal.get('stop_loss', 0):.2f}
止盈价格: {signal.get('take_profit', 0):.2f}
盈亏比: {signal.get('risk_reward_ratio', 0):.2f}:1
推荐杠杆: {signal.get('recommended_leverage', 1)}x

【市场分析】
阶段: {llm_analysis.market_phase}
趋势强度: {llm_analysis.trend_strength}
市场情绪: {llm_analysis.sentiment}
关键观察: {llm_analysis.key_observation}

【技术依据】
{llm_analysis.reasoning}

【要求】
1. 标题醒目，包含资产名称和信号类型
2. 第一段简明扼要说明信号类型和强度
3. 第二段解释技术面支撑逻辑（引用具体指标）
4. 第三段列出交易计划（入场/止损/止盈）
5. 第四段强调风险提示
6. 专业但不失可读性
7. 适当使用emoji增强视觉效果（每段最多1个）
8. 总字数200-300字

直接输出快讯内容，不要有任何前缀说明。"""

        elif style == "beginner":
            return f"""请为新手交易者生成一条通俗易懂的交易快讯（400-500字）：

【信号信息】
类型: {signal['signal']} ({'买入' if signal['signal'] == 'BUY' else '卖出' if signal['signal'] == 'SELL' else '观望'})
强度: {signal.get('strength', 0):.1f}%
建议价格: {signal.get('entry_price', 0):.2f}

【市场情况】
{llm_analysis.key_observation}

【要求】
1. 用"朋友们好"开头，亲切友好的语气
2. 避免使用专业术语，用生活化比喻解释
3. 逐步解释为什么出现这个信号（用1234列举）
4. 详细说明怎么操作（分批买入、止损设置）
5. 用❌和✅列出注意事项
6. 结尾鼓励但提醒风险
7. 丰富使用emoji（但不要过度）
8. 总字数400-500字

直接输出快讯内容，不要有任何前缀说明。"""

        elif style == "social_media":
            return f"""请生成一条适合Twitter/微博的简短交易快讯（100-150字）：

【信号】{signal['signal']} | 强度: {signal.get('strength', 0):.0f}%
【入场】{signal.get('entry_price', 0):.2f}
【目标】{signal.get('take_profit', 0):.2f}
【止损】{signal.get('stop_loss', 0):.2f}

【要求】
1. 开头用醒目emoji（🚨/📈/📉）
2. 核心信息用emoji分隔（📍/🎯/🛡️）
3. 简明列出技术依据（3-4条，每条1行）
4. 包含策略建议（杠杆/仓位）
5. 风险提示1句
6. 结尾包含话题标签 #BTC #Trading
7. 总字数100-150字

直接输出快讯内容，不要有任何前缀说明。"""

        else:
            return PromptTemplates.market_analysis(context)
    
    @staticmethod
    def risk_assessment(signal: dict, context: MarketContext) -> str:
        """风险评估提示词"""
        return f"""请对以下交易信号进行全面风险评估：

【信号信息】
类型: {signal['signal']}
入场: {signal.get('entry_price', 0):.2f}
止损: {signal.get('stop_loss', 0):.2f}
止盈: {signal.get('take_profit', 0):.2f}
杠杆: {signal.get('recommended_leverage', 1)}x

【市场环境】
价格: {context.current_price:.2f}
波动率: {context.volatility}
支撑位: {context.support_levels}
阻力位: {context.resistance_levels}

请评估以下维度的风险并给出建议：
1. 技术面风险
2. 市场环境风险
3. 流动性风险
4. 黑天鹅事件风险

用JSON格式返回：
{{
  "overall_risk": "low/medium/high",
  "risk_factors": ["风险点1", "风险点2", ...],
  "mitigation_strategies": ["应对策略1", "应对策略2", ...],
  "position_advice": "仓位建议"
}}"""


class LLMEnhancedStrategy(AlphaTrendStrategy):
    """LLM增强的Alpha Trend策略"""
    
    def __init__(
        self,
        enable_llm: bool = True,
        **kwargs: Any
    ):
        super().__init__(**kwargs)
        self.enable_llm = enable_llm
        self.llm = LLMProvider() if enable_llm else None
        self.prompts = PromptTemplates()
    
    def _build_market_context(self, df: DataFrame, index: int = -1) -> MarketContext:
        """构建市场上下文"""
        current = df.iloc[index]
        prev_1d = df.iloc[max(0, index - 1)]
        prev_7d = df.iloc[max(0, index - 7)]
        
        # 计算涨跌幅
        change_24h = ((current['close'] - prev_1d['close']) / prev_1d['close']) * 100
        change_7d = ((current['close'] - prev_7d['close']) / prev_7d['close']) * 100
        
        # RSI状态
        rsi = current['rsi']
        if rsi < 30:
            rsi_status = "oversold"
        elif rsi > 70:
            rsi_status = "overbought"
        else:
            rsi_status = "neutral"
        
        # MACD信号
        if current['macd'] > current['macd_signal']:
            macd_signal = "bullish"
        elif current['macd'] < current['macd_signal']:
            macd_signal = "bearish"
        else:
            macd_signal = "neutral"
        
        # Alpha Trend方向
        alpha_direction = "up" if current['alpha_trend_direction'] == 1 else "down"
        
        # 波动率评估
        atr_pct = (current['atr'] / current['close']) * 100
        if atr_pct > 5:
            volatility = "high"
        elif atr_pct > 2:
            volatility = "medium"
        else:
            volatility = "low"
        
        return MarketContext(
            current_price=current['close'],
            price_change_24h=change_24h,
            price_change_7d=change_7d,
            alpha_trend_value=current['alpha_trend'],
            alpha_trend_direction=alpha_direction,
            rsi=rsi,
            rsi_status=rsi_status,
            macd_signal=macd_signal,
            volume_ratio=current['volume_ratio'],
            support_levels=[current['support1'], current['support2']],
            resistance_levels=[current['resistance1'], current['resistance2']],
            volatility=volatility
        )
    
    def _call_llm_analysis(self, context: MarketContext) -> LLMAnalysis:
        """调用LLM进行市场分析"""
        if not self.enable_llm or not self.llm:
            # 返回默认分析
            return LLMAnalysis(
                market_phase="unknown",
                trend_strength="medium",
                sentiment="neutral",
                key_observation="LLM分析未启用",
                confidence=0.5,
                reasoning="基于技术指标的默认分析"
            )
        
        prompt = self.prompts.market_analysis(context)
        
        messages = [
            {
                "role": "system",
                "content": "你是专业的量化交易分析师，精通技术分析。请严格按照JSON格式返回分析结果。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            response = self.llm.generate(messages, max_tokens=1000)
            
            # 清理响应（移除可能的markdown标记）
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1]
                response = response.rsplit("\n", 1)[0]
            response = response.replace("```json", "").replace("```", "").strip()
            
            # 解析JSON
            result = json.loads(response)
            
            return LLMAnalysis(
                market_phase=result.get('market_phase', 'unknown'),
                trend_strength=result.get('trend_strength', 'medium'),
                sentiment=result.get('sentiment', 'neutral'),
                key_observation=result.get('key_observation', ''),
                confidence=float(result.get('confidence', 0.5)),
                reasoning=result.get('reasoning', '')
            )
            
        except Exception as e:
            print(f"⚠️  LLM分析失败: {e}")
            return LLMAnalysis(
                market_phase="unknown",
                trend_strength="medium",
                sentiment="neutral",
                key_observation="LLM分析出错，请以技术指标为准",
                confidence=0.3,
                reasoning=f"错误: {str(e)}"
            )
    
    def generate_news_flash(
        self,
        signal: dict,
        context: MarketContext,
        llm_analysis: LLMAnalysis,
        style: str = "professional"
    ) -> NewsFlash:
        """生成交易快讯"""
        if not self.enable_llm or not self.llm:
            # 返回简单快讯
            content = self._generate_simple_flash(signal, context)
        else:
            prompt = self.prompts.generate_flash(signal, context, llm_analysis, style)
            
            messages = [
                {
                    "role": "system",
                    "content": "你是专业的财经新闻编辑，擅长将技术分析转化为易读的交易快讯。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            try:
                content = self.llm.generate(messages, max_tokens=1500)
            except Exception as e:
                print(f"⚠️  快讯生成失败: {e}")
                content = self._generate_simple_flash(signal, context)
        
        # 生成标题
        asset_name = "BTC"  # 可以从配置中获取
        title = f"【{asset_name}交易信号】{signal['signal']}"
        
        return NewsFlash(
            title=title,
            content=content,
            style=style,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            signal_type=signal['signal']
        )
    
    def _generate_simple_flash(self, signal: dict, context: MarketContext) -> str:
        """生成简单快讯（LLM不可用时）"""
        if signal['signal'] == 'HOLD':
            return "当前无明确交易信号，建议观望。"
        
        direction = "做多" if signal['signal'] == 'BUY' else "做空"
        
        flash = f"""【{signal['signal']}信号】

信号强度: {signal.get('strength', 0):.1f}%
当前价格: {context.current_price:.2f}

入场价格: {signal.get('entry_price', 0):.2f}
止损价格: {signal.get('stop_loss', 0):.2f}
止盈价格: {signal.get('take_profit', 0):.2f}
盈亏比: {signal.get('risk_reward_ratio', 0):.2f}:1

推荐杠杆: {signal.get('recommended_leverage', 1)}x

风险提示: 严格执行止损，分批建仓。
"""
        return flash.strip()
    
    def analyze_with_llm(
            self,
            df: DataFrame,
            index: int = -1,
            total_capital: float = 10000,
            generate_flash: bool = True,
            flash_style: str = "professional"
        ) -> dict:
        """
        使用LLM增强的策略分析
        
        返回:
            包含原始信号 + LLM分析 + 快讯的完整结果
        """
        # 1. 计算技术指标
        df = self.calculate_indicators(df)
        
        # 2. 生成基础信号
        base_signal = self.generate_signal(df, index, total_capital)
        
        # 3. 构建市场上下文
        context = self._build_market_context(df, index)
        
        # 4. LLM市场分析
        llm_analysis = self._call_llm_analysis(context)
        
        # 5. 生成快讯（如果需要）
        news_flash = None
        if generate_flash and base_signal['signal'] != 'HOLD':
            news_flash = self.generate_news_flash(
                base_signal, context, llm_analysis, flash_style
            )
        
        # 6. 组合结果
        enhanced_signal = {
            **base_signal,
            'market_context': context.to_dict(),
            'llm_analysis': llm_analysis.to_dict(),
            'news_flash': news_flash.to_dict() if news_flash else None
        }
        
        return enhanced_signal


def llm_enhanced_strategy(
    df: DataFrame,
    total_capital: float = 10000,
    enable_llm: bool = True,
    flash_style: str = "professional",
    **strategy_params: Any
) -> dict:
    """
    LLM增强策略的便捷函数
    
    参数:
        df: 市场数据
        total_capital: 总资金
        enable_llm: 是否启用LLM
        flash_style: 快讯风格 ("professional"/"beginner"/"social_media")
        **strategy_params: 其他策略参数
    
    返回:
        包含信号、分析、快讯的完整结果
    """
    strategy = LLMEnhancedStrategy(
        enable_llm=enable_llm,
        **strategy_params
    )
    
    result = strategy.analyze_with_llm(
        df,
        total_capital=total_capital,
        flash_style=flash_style
    )
    
    return result


def print_enhanced_signal(result: dict):
    """打印LLM增强的信号"""
    print("\n" + "="*80)
    print("LLM增强的交易分析")
    print("="*80)
    
    # 基础信号
    print(f"\n【交易信号】{result['signal']}")
    if result['signal'] != 'HOLD':
        print(f"信号强度: {result.get('strength', 0):.1f}%")
        print(f"入场价格: {result.get('entry_price', 0):.2f}")
        print(f"止损价格: {result.get('stop_loss', 0):.2f}")
        print(f"止盈价格: {result.get('take_profit', 0):.2f}")
        print(f"盈亏比: {result.get('risk_reward_ratio', 0):.2f}:1")
        print(f"推荐杠杆: {result.get('recommended_leverage', 1)}x")
    
    # LLM分析
    if 'llm_analysis' in result:
        analysis = result['llm_analysis']
        print(f"\n【LLM市场分析】")
        print(f"市场阶段: {analysis['market_phase']}")
        print(f"趋势强度: {analysis['trend_strength']}")
        print(f"市场情绪: {analysis['sentiment']}")
        print(f"关键观察: {analysis['key_observation']}")
        print(f"置信度: {analysis['confidence']:.0%}")
        if analysis.get('reasoning'):
            print(f"\n推理过程:\n{analysis['reasoning']}")
    
    # 快讯
    if result.get('news_flash'):
        flash = result['news_flash']
        print(f"\n{'='*80}")
        print(f"【交易快讯】{flash['style']} 风格")
        print("="*80)
        print(flash['content'])
        print(f"\n生成时间: {flash['timestamp']}")
        print("="*80)


if __name__ == "__main__":
    print("LLM增强策略已加载")
    print("\n使用 OpenAI GPT API")
    print("\n使用示例:")
    print("result = llm_enhanced_strategy(df)")
    print("print_enhanced_signal(result)")
