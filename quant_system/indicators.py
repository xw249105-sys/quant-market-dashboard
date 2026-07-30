from __future__ import annotations

import numpy as np
import pandas as pd


def add_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """使用 pandas 计算指标，不依赖 TA-Lib。"""
    df = data.copy().sort_values("date").reset_index(drop=True)
    close, high, low = df["close"], df["high"], df["low"]

    for window in (20, 60, 120):
        df[f"ma{window}"] = close.rolling(window).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi14"] = (100 - 100 / (1 + rs)).fillna(50)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    df["atr14"] = true_range.rolling(14).mean()
    df["volume_ma20"] = df["volume"].rolling(20).mean()
    df["return_20"] = close.pct_change(20)
    return df

