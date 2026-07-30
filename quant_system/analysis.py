from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from .indicators import add_indicators


@dataclass(frozen=True)
class AnalysisResult:
    symbol: str
    date: str
    price: float
    score: int
    signal: str
    buy_low: float
    buy_high: float
    stop_loss: float
    target: float
    risk: str
    reasons: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def score_row(row: pd.Series) -> tuple[int, list[str]]:
    score, reasons = 0, []

    if row["close"] > row["ma20"]:
        score += 15
        reasons.append("收盘价站上 MA20")
    if row["ma20"] > row["ma60"]:
        score += 15
        reasons.append("MA20 高于 MA60")
    if row["ma60"] > row["ma120"]:
        score += 10
        reasons.append("中长期均线多头")

    if 40 <= row["rsi14"] <= 65:
        score += 15
        reasons.append("RSI 位于健康区间")
    elif row["rsi14"] < 35:
        score += 8
        reasons.append("RSI 偏低，存在超跌特征")

    if row["macd"] > row["macd_signal"]:
        score += 15
        reasons.append("MACD 位于信号线上方")
    if row["volume"] > row["volume_ma20"]:
        score += 10
        reasons.append("成交量高于 20 日均量")
    if row["return_20"] > 0:
        score += 10
        reasons.append("20 日动量为正")

    atr_ratio = row["atr14"] / row["close"]
    if atr_ratio <= 0.025:
        score += 10
        reasons.append("近期波动可控")
    elif atr_ratio <= 0.04:
        score += 5

    return min(score, 100), reasons


def analyze(data: pd.DataFrame, symbol: str) -> AnalysisResult:
    df = add_indicators(data).dropna()
    if df.empty or len(data) < 121:
        raise ValueError("至少需要 121 条有效日线数据")

    row = df.iloc[-1]
    score, reasons = score_row(row)
    price, atr = float(row["close"]), float(row["atr14"])
    if score >= 75:
        signal = "分批买入观察"
    elif score >= 55:
        signal = "持有/等待确认"
    elif score >= 35:
        signal = "谨慎观望"
    else:
        signal = "回避/考虑减仓"

    atr_ratio = atr / price
    risk = "低" if atr_ratio <= 0.02 else "中" if atr_ratio <= 0.04 else "高"
    return AnalysisResult(
        symbol=symbol,
        date=row["date"].strftime("%Y-%m-%d"),
        price=round(price, 3),
        score=score,
        signal=signal,
        buy_low=round(max(price - atr, 0), 3),
        buy_high=round(price, 3),
        stop_loss=round(max(price - 2 * atr, 0), 3),
        target=round(price + 3 * atr, 3),
        risk=risk,
        reasons=reasons,
    )

