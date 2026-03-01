"""复合策略 - 组合多个指标进行综合分析"""
from pandas import DataFrame
from typing import Any, TypedDict

from indicators import IndicatorRegistry, IndicatorSummaryOutput


class StrategySummary(TypedDict):
    """策略汇总输出"""
    indicators: list[IndicatorSummaryOutput]
    latest_price: float
    latest_time: str
    score_matrix: dict[str, dict[str, Any]]
    total_score: int
    decision: str


class CompositeStrategy:
    """
    复合策略 - 支持插件式指标组合
    
    用法:
        strategy = CompositeStrategy()  # 使用所有注册指标
        strategy = CompositeStrategy(indicator_names=['rsi', 'macd'])  # 指定指标
    """
    
    def __init__(self, indicator_names: list[str] | None = None):
        """
        初始化复合策略
        
        Args:
            indicator_names: 指定要使用的指标名称列表，None表示使用所有已注册指标
        """
        # 确保指标已注册
        IndicatorRegistry.initialize()
        
        if indicator_names:
            self.indicators = []
            for name in indicator_names:
                indicator = IndicatorRegistry.get(name)
                if indicator is not None:
                    self.indicators.append(indicator)
            if len(self.indicators) != len(indicator_names):
                missing = set(indicator_names) - set(IndicatorRegistry.names())
                raise ValueError(f"未找到指标: {missing}")
        else:
            default_names = ["ma", "alpha_trend", "bollinger", "macd", "volume", "atr"]
            self.indicators = []
            for name in default_names:
                indicator = IndicatorRegistry.get(name)
                if indicator is not None:
                    self.indicators.append(indicator)

    @staticmethod
    def _to_values(ind: IndicatorSummaryOutput) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for attr in dir(ind):
            if attr.startswith('_'):
                continue
            value = getattr(ind, attr)
            if callable(value):
                continue
            values[attr] = value
        return values

    @staticmethod
    def _score_trend(ma_values: dict[str, Any], at_values: dict[str, Any]) -> dict[str, Any]:
        score = 0
        reasons: list[str] = []

        alignment = ma_values.get("alignment")
        if alignment == "bullish":
            score += 1
            reasons.append("MA多头排列")
        elif alignment == "bearish":
            score -= 1
            reasons.append("MA空头排列")
        else:
            reasons.append("MA中性")

        overall = at_values.get("overall")
        if overall == "bullish":
            score += 1
            reasons.append("AT整体偏多")
        elif overall == "bearish":
            score -= 1
            reasons.append("AT整体偏空")
        else:
            reasons.append("AT中性/偏弱")

        return {"score": score, "reason": "，".join(reasons)}

    @staticmethod
    def _score_structure(boll_values: dict[str, Any], trend_score: int) -> dict[str, Any]:
        zone = boll_values.get("zone", "middle")
        squeeze_state = boll_values.get("squeeze_state", "normal")

        if trend_score > 0:
            if zone in {"below_lower", "near_lower", "middle"}:
                score = 1
                reason = "多头环境下位置合理"
            else:
                score = -1
                reason = "多头环境下位置偏高"
        elif trend_score < 0:
            if zone in {"above_upper", "near_upper", "middle"}:
                score = 1
                reason = "空头环境下位置合理"
            else:
                score = -1
                reason = "空头环境下位置偏低"
        else:
            score = 0
            reason = "趋势不明确，结构中性"

        if squeeze_state == "compressed":
            reason = f"{reason}，带宽压缩"

        return {"score": score, "reason": reason}

    @staticmethod
    def _score_momentum(macd_values: dict[str, Any]) -> dict[str, Any]:
        if bool(macd_values.get("divergence_warning", False)):
            return {"score": -2, "reason": "MACD出现背离预警"}

        support = macd_values.get("momentum_support")
        if support == "support":
            return {"score": 1, "reason": "MACD动量支持趋势"}

        return {"score": 0, "reason": "MACD动量中性"}

    @staticmethod
    def _score_flow(volume_values: dict[str, Any], trend_score: int) -> dict[str, Any]:
        ratio = float(volume_values.get("ratio", 0) or 0)
        obv_trend = volume_values.get("obv_trend", "flat")

        if ratio >= 1.0:
            if trend_score > 0 and obv_trend == "inflow":
                return {"score": 1, "reason": "放量且OBV流入，资金支持多头"}
            if trend_score < 0 and obv_trend == "outflow":
                return {"score": 1, "reason": "放量且OBV流出，资金支持空头"}
            if obv_trend in {"inflow", "outflow"}:
                return {"score": -1, "reason": "放量但资金方向与趋势不一致"}
            return {"score": 0, "reason": "放量但资金方向不清晰"}

        if ratio < 0.6:
            return {"score": 0, "reason": "缩量，参与度不足"}

        return {"score": 0, "reason": "量能中性"}

    @staticmethod
    def _score_volatility(atr_values: dict[str, Any]) -> dict[str, Any]:
        atr_percent = float(atr_values.get("atr_percent", 0) or 0)
        if atr_percent > 5:
            return {"score": -1, "reason": "波动率过高，需降风险"}
        return {"score": 0, "reason": "波动率正常"}

    def _build_score_matrix(self, summaries: list[IndicatorSummaryOutput]) -> tuple[dict[str, dict[str, Any]], int, str]:
        by_name: dict[str, dict[str, Any]] = {}
        for summary in summaries:
            name = getattr(summary, "name", None)
            if isinstance(name, str):
                by_name[name] = self._to_values(summary)

        trend = self._score_trend(by_name.get("ma", {}), by_name.get("alpha_trend", {}))
        structure = self._score_structure(by_name.get("bollinger", {}), int(trend["score"]))
        momentum = self._score_momentum(by_name.get("macd", {}))
        flow = self._score_flow(by_name.get("volume", {}), int(trend["score"]))
        volatility = self._score_volatility(by_name.get("atr", {}))

        score_matrix = {
            "trend": trend,
            "structure": structure,
            "momentum": momentum,
            "flow": flow,
            "volatility": volatility,
        }
        total_score = int(sum(int(v["score"]) for v in score_matrix.values()))

        if total_score >= 3:
            decision = "high_confidence"
        elif total_score >= 1:
            decision = "reduced_or_wait"
        else:
            decision = "no_entry"

        return score_matrix, total_score, decision
    
    def calculate_all(self, df: DataFrame) -> DataFrame:
        """
        计算所有指标
        
        Args:
            df: OHLCV数据
            
        Returns:
            添加了所有指标列的DataFrame
        """
        for indicator in self.indicators:
            df = indicator.calculate(df)
        return df
    
    def generate_summary(self, df: DataFrame) -> StrategySummary:
        """
        生成所有指标的摘要
        
        Args:
            df: 已计算指标的DataFrame
            
        Returns:
            包含所有指标摘要的汇总
        """
        summaries = []
        for indicator in self.indicators:
            try:
                summary = indicator.summarize(df)
                summaries.append(summary)
            except Exception as e:
                pass

        score_matrix, total_score, decision = self._build_score_matrix(summaries)

        last_index = df.index[-1]
        return {
            "indicators": summaries,
            "latest_price": float(df.at[last_index, "close"]),
            "latest_time": str(df.at[last_index, "datetime"]),
            "score_matrix": score_matrix,
            "total_score": total_score,
            "decision": decision,
        }
    
    def get_all_column_names(self) -> list[str]:
        """获取所有指标生成的列名"""
        columns = []
        for indicator in self.indicators:
            columns.extend(indicator.get_column_names())
        return columns
    
    @property
    def indicator_names(self) -> list[str]:
        """获取当前策略使用的指标名称"""
        return [ind.name for ind in self.indicators]
