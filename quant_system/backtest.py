from __future__ import annotations

import pandas as pd

from .analysis import score_row
from .indicators import add_indicators


def run_backtest(
    data: pd.DataFrame,
    buy_score: int = 75,
    sell_score: int = 45,
    fee_rate: float = 0.0005,
) -> dict:
    """无未来函数的收盘信号回测；信号在下一交易日开盘执行。"""
    df = add_indicators(data).dropna().reset_index(drop=True)
    scores = [score_row(row)[0] for _, row in df.iterrows()]
    cash, shares, trades = 1.0, 0.0, 0
    equity_curve = []

    for index in range(1, len(df)):
        previous_score = scores[index - 1]
        open_price = float(df.iloc[index]["open"])
        if shares == 0 and previous_score >= buy_score:
            shares = cash * (1 - fee_rate) / open_price
            cash, trades = 0.0, trades + 1
        elif shares > 0 and previous_score < sell_score:
            cash = shares * open_price * (1 - fee_rate)
            shares, trades = 0.0, trades + 1
        equity_curve.append(cash + shares * float(df.iloc[index]["close"]))

    if not equity_curve:
        raise ValueError("可用于回测的数据不足")
    equity = pd.Series(equity_curve)
    running_max = equity.cummax()
    max_drawdown = float((equity / running_max - 1).min())
    buy_hold = float(df.iloc[-1]["close"] / df.iloc[1]["open"] - 1)
    return {
        "strategy_return": round(float(equity.iloc[-1] - 1), 4),
        "buy_hold_return": round(buy_hold, 4),
        "max_drawdown": round(max_drawdown, 4),
        "trade_count": trades,
    }

