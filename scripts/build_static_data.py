from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import akshare as ak
import feedparser
import pandas as pd

from quant_system import analyze
from quant_system.data import fetch_akshare

OUTPUT = Path("site/data.json")
SHANGHAI = ZoneInfo("Asia/Shanghai")

WATCHLIST = {
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "159915": "创业板ETF",
    "518880": "黄金ETF",
    "513100": "纳指ETF",
    "513500": "标普500ETF",
    "159920": "恒生ETF",
    "600519": "贵州茅台",
    "300750": "宁德时代",
}

RSS_SOURCES = [
    ("人民网", "http://www.people.com.cn/rss/politics.xml", "全国要闻"),
    ("人民网财经", "http://www.people.com.cn/rss/finance.xml", "财经"),
]


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def text(row, *columns, default=""):
    for column in columns:
        value = row.get(column)
        if value is not None and str(value) != "nan":
            return str(value)
    return default


def load_previous() -> dict:
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def fetch_universe() -> list[dict]:
    items: dict[tuple[str, str], dict] = {}
    loaders = [
        ("A股", ak.stock_zh_a_spot_em, ("代码",), ("名称",)),
        ("ETF", ak.fund_etf_spot_em, ("代码",), ("名称",)),
        ("港股", ak.stock_hk_spot_em, ("代码", "symbol"), ("名称", "name")),
        ("美股", ak.stock_us_spot_em, ("代码", "symbol"), ("名称", "name", "中文名称")),
    ]
    for market, loader, code_columns, name_columns in loaders:
        try:
            frame = loader()
        except Exception:
            continue
        for _, row in frame.iterrows():
            symbol = text(row, *code_columns)
            name = text(row, *name_columns)
            if symbol and name:
                items[(market, symbol)] = {
                    "symbol": symbol,
                    "name": name,
                    "type": market,
                    "alias": name.replace("股份", "").replace("集团", ""),
                }
    return list(items.values())


def fetch_indices() -> list[dict]:
    wanted = {
        "上证指数", "深证成指", "创业板指", "科创50",
        "恒生指数", "日经225", "标普500", "纳斯达克", "道琼斯",
    }
    results: dict[str, dict] = {}
    loaders = [
        lambda: ak.stock_zh_index_spot_em(symbol="上证系列指数"),
        lambda: ak.stock_zh_index_spot_em(symbol="深证系列指数"),
        getattr(ak, "index_global_spot_em", None),
    ]
    for loader in loaders:
        if loader is None:
            continue
        try:
            frame = loader()
        except Exception:
            continue
        for _, row in frame.iterrows():
            name = text(row, "名称", "name")
            if name in wanted:
                results[name] = {
                    "name": name,
                    "price": number(row.get("最新价", row.get("最新报价"))),
                    "change": number(row.get("涨跌幅")),
                }
    return list(results.values())


def fetch_sectors() -> tuple[dict, dict]:
    frame = ak.stock_board_industry_name_em()
    frame["涨跌幅"] = pd.to_numeric(frame["涨跌幅"], errors="coerce")
    frame = frame.dropna(subset=["涨跌幅"]).sort_values("涨跌幅", ascending=False)
    breadth = {
        "up": int(pd.to_numeric(frame.get("上涨家数"), errors="coerce").fillna(0).sum()),
        "down": int(pd.to_numeric(frame.get("下跌家数"), errors="coerce").fillna(0).sum()),
    }

    def convert(rows):
        return [
            {
                "name": text(row, "板块名称"),
                "change": number(row.get("涨跌幅")),
                "leader": text(row, "领涨股票", default="—"),
            }
            for _, row in rows.iterrows()
        ]

    return breadth, {
        "gainers": convert(frame.head(8)),
        "losers": convert(frame.tail(8).sort_values("涨跌幅")),
    }


def fetch_news() -> list[dict]:
    items: list[dict] = []
    financial_loaders = [
        ("东方财富", getattr(ak, "stock_info_global_em", None), "财经"),
        ("新浪财经", getattr(ak, "stock_info_global_sina", None), "财经"),
    ]
    for source, loader, category in financial_loaders:
        if loader is None:
            continue
        try:
            frame = loader().head(25)
        except Exception:
            continue
        for _, row in frame.iterrows():
            title = text(row, "标题")
            if title:
                items.append({
                    "time": text(row, "发布时间", "时间")[-5:],
                    "title": title,
                    "source": source,
                    "category": category,
                    "url": text(row, "链接", default="#"),
                })

    for source, url, category in RSS_SOURCES:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        for entry in feed.entries[:20]:
            items.append({
                "time": text(entry, "published", "updated")[-5:],
                "title": text(entry, "title"),
                "source": source,
                "category": category,
                "url": text(entry, "link", default="#"),
            })

    deduplicated, seen = [], set()
    for item in items:
        key = item["title"].strip()
        if key and key not in seen:
            seen.add(key)
            deduplicated.append(item)
    return deduplicated[:50]


def fetch_quant_assets() -> list[dict]:
    assets = []
    for symbol, name in WATCHLIST.items():
        try:
            result = analyze(fetch_akshare(symbol), symbol).to_dict()
            result["name"] = name
            if result["score"] >= 75:
                result["action"] = "可在参考区间小仓分批观察，不宜一次满仓"
            elif result["score"] >= 55:
                result["action"] = "暂不追买，等待趋势与成交量进一步确认"
            else:
                result["action"] = "当前不建议新开仓，优先控制风险"
            assets.append(result)
        except Exception:
            continue
    return sorted(assets, key=lambda item: item["score"], reverse=True)


def main() -> None:
    previous = load_previous()
    errors = []

    def safe(name, loader, fallback):
        try:
            value = loader()
            return value if value else fallback
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            return fallback

    universe = safe("证券目录", fetch_universe, previous.get("universe", []))
    indices = safe("指数", fetch_indices, previous.get("indices", []))
    breadth, sectors = safe(
        "板块",
        fetch_sectors,
        (previous.get("breadth", {"up": 0, "down": 0}), previous.get("sectors", {"gainers": [], "losers": []})),
    )
    news = safe("新闻", fetch_news, previous.get("news", []))
    assets = safe("量化", fetch_quant_assets, previous.get("assets", []))

    if not any((universe, indices, news, assets)):
        raise RuntimeError("全部数据源均不可用")

    now = datetime.now(SHANGHAI)
    payload = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        "market_status": "公开数据源，可能延迟",
        "breadth": breadth,
        "indices": indices,
        "sectors": sectors,
        "universe": universe,
        "assets": assets,
        "news": news,
        "health": {"partial_failures": errors},
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
