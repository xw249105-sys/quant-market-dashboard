from __future__ import annotations

from pathlib import Path

import pandas as pd

STANDARD_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
CHINESE_COLUMNS = {
    "日期": "date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
}


def _normalize(data: pd.DataFrame) -> pd.DataFrame:
    df = data.rename(columns=CHINESE_COLUMNS).copy()
    missing = set(STANDARD_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"行情缺少字段: {', '.join(sorted(missing))}")
    df = df[STANDARD_COLUMNS]
    df["date"] = pd.to_datetime(df["date"])
    for column in STANDARD_COLUMNS[1:]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)


def load_csv(path: str | Path) -> pd.DataFrame:
    return _normalize(pd.read_csv(path))


def fetch_akshare(symbol: str, start_date: str = "20180101") -> pd.DataFrame:
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("尚未安装 AkShare，请先执行 pip install -r requirements.txt") from exc

    raw = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        adjust="qfq",
    )
    if raw.empty:
        raise RuntimeError(f"未获取到 {symbol} 的行情，请检查代码或网络")
    return _normalize(raw)


def load_market_data(
    symbol: str,
    csv_path: str | Path | None = None,
    cache_dir: str | Path = "data",
    refresh: bool = False,
) -> pd.DataFrame:
    """优先读指定 CSV；其次读缓存；最后联网获取并缓存。"""
    if csv_path:
        return load_csv(csv_path)

    cache = Path(cache_dir) / f"{symbol}.csv"
    if cache.exists() and not refresh:
        return load_csv(cache)

    data = fetch_akshare(symbol)
    cache.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(cache, index=False)
    return data

