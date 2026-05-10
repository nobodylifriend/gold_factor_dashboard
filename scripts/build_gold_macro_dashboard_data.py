from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "visuals" / "gold_macro_dashboard" / "data" / "dashboard_data.json"

DASHBOARD_SERIES = {
    "xau": {
        "path": ROOT / "data" / "xau" / "xau_usd_daily_ohlc.csv",
        "value_column": "close",
        "label": "黄金价格走势",
        "frequency_label": "日频",
    },
    "sp500": {
        "path": ROOT / "data" / "stock_index" / "SP500.csv",
        "value_column": "value",
        "label": "标普500价格走势",
        "frequency_label": "日频",
    },
    "nasdaq100": {
        "path": ROOT / "data" / "stock_index" / "NASDAQ100.csv",
        "value_column": "value",
        "label": "纳斯达克100价格走势",
        "frequency_label": "日频",
    },
    "tips10y": {
        "path": ROOT / "data" / "fred" / "名义利率" / "10年期TIPS实际收益率.csv",
        "value_column": "value",
        "label": "10年期TIPS实际收益率",
        "frequency_label": "日频",
    },
    "dxy": {
        "path": ROOT / "data" / "fx" / "DXY.csv",
        "value_column": "close",
        "label": "美元指数 DXY",
        "frequency_label": "日频",
    },
    "nominal10y": {
        "path": ROOT / "data" / "fred" / "名义利率" / "10年期美债收益率.csv",
        "value_column": "value",
        "label": "10年期美债收益率",
        "frequency_label": "日频",
    },
    "breakeven10y": {
        "path": ROOT / "data" / "fred" / "通胀_通胀预期" / "10年盈亏平衡通胀率.csv",
        "value_column": "value",
        "label": "10年盈亏平衡通胀率",
        "frequency_label": "日频",
    },
    "credit_oas_hy": {
        "path": ROOT / "data" / "fred" / "信用利差" / "高收益信用利差_OAS.csv",
        "value_column": "value",
        "label": "高收益信用利差 OAS",
        "frequency_label": "日频",
    },
    "sofr": {
        "path": ROOT / "data" / "fred" / "名义利率" / "SOFR.csv",
        "value_column": "value",
        "label": "SOFR",
        "frequency_label": "日频",
    },
    "xau_monthly": {
        "path": ROOT / "data" / "xau" / "xau_usd_monthly_close.csv",
        "value_column": "close",
        "label": "黄金月度收盘价",
        "frequency_label": "月频",
    },
    "gvz": {
        "path": ROOT / "data" / "xau" / "GVZ.csv",
        "value_column": "value",
        "label": "黄金波动率 GVZ",
        "frequency_label": "日频",
    },
    "gld_holdings": {
        "path": ROOT / "data" / "xau" / "GLD_total_holdings_tonnes.csv",
        "value_column": "value",
        "label": "GLD 黄金总持仓",
        "frequency_label": "日频",
    },
    "global_gold_etf_holdings_weekly": {
        "path": ROOT / "data" / "xau" / "global_gold_etf_holdings_weekly.csv",
        "value_column": "value",
        "label": "全球黄金ETF持仓（周）",
        "frequency_label": "周频",
    },
    "gold_etf_flows": {
        "path": ROOT / "data" / "xau" / "global_gold_etf_net_flows_monthly.csv",
        "value_column": "value",
        "label": "全球黄金ETF净流量",
        "frequency_label": "月频",
    },
    "global_gold_etf_flows_weekly": {
        "path": ROOT / "data" / "xau" / "global_gold_etf_net_flows_weekly.csv",
        "value_column": "value",
        "label": "全球黄金ETF净流量（周）",
        "frequency_label": "周频",
    },
    "gld_volume": {
        "path": ROOT / "data" / "xau" / "GLD_share_volume.csv",
        "value_column": "value",
        "label": "GLD成交量",
        "frequency_label": "日频",
    },
    "global_gold_mine_production_quarterly": {
        "path": ROOT / "data" / "xau" / "global_gold_mine_production_quarterly.csv",
        "value_column": "value",
        "label": "全球矿产金产量（季）",
        "frequency_label": "季频",
    },
    "global_gold_aisc_quarterly": {
        "path": ROOT / "data" / "xau" / "global_gold_aisc_quarterly.csv",
        "value_column": "value",
        "label": "全球黄金AISC（季）",
        "frequency_label": "季频",
    },
    "official_gold_reserve_change_quarterly": {
        "path": ROOT / "data" / "xau" / "change_in_official_gold_reserves_quarterly.csv",
        "value_column": "value",
        "label": "官方黄金储备变化（季）",
        "frequency_label": "季频",
    },
    "tips5y": {
        "path": ROOT / "data" / "fred" / "名义利率" / "5年期TIPS实际收益率.csv",
        "value_column": "value",
        "label": "5年期TIPS实际收益率",
        "frequency_label": "日频",
    },
    "tips30y": {
        "path": ROOT / "data" / "fred" / "名义利率" / "30年期TIPS实际收益率.csv",
        "value_column": "value",
        "label": "30年期TIPS实际收益率",
        "frequency_label": "日频",
    },
    "fedfunds": {
        "path": ROOT / "data" / "fred" / "名义利率" / "联邦基金利率.csv",
        "value_column": "value",
        "label": "联邦基金利率",
        "frequency_label": "月频",
    },
    "tbill3m": {
        "path": ROOT / "data" / "fred" / "名义利率" / "3个月美债收益率.csv",
        "value_column": "value",
        "label": "3个月美债收益率",
        "frequency_label": "月频",
    },
    "m2": {
        "path": ROOT / "data" / "fred" / "货币供应量指标" / "M2.csv",
        "value_column": "value",
        "label": "M2",
        "frequency_label": "月频",
    },
    "breakeven5y": {
        "path": ROOT / "data" / "fred" / "通胀_通胀预期" / "5年盈亏平衡通胀率.csv",
        "value_column": "value",
        "label": "5年盈亏平衡通胀率",
        "frequency_label": "日频",
    },
    "forward5y5y": {
        "path": ROOT / "data" / "fred" / "通胀_通胀预期" / "5年期5年期前瞻通胀预期.csv",
        "value_column": "value",
        "label": "5年期5年期前瞻通胀预期",
        "frequency_label": "日频",
    },
    "cpi_yoy": {
        "path": ROOT / "data" / "fred" / "通胀_通胀预期" / "CPI_同比.csv",
        "value_column": "value",
        "label": "CPI同比",
        "frequency_label": "月频",
    },
    "core_cpi_yoy": {
        "path": ROOT / "data" / "fred" / "通胀_通胀预期" / "核心CPI_同比.csv",
        "value_column": "value",
        "label": "核心CPI同比",
        "frequency_label": "月频",
    },
    "pce_yoy": {
        "path": ROOT / "data" / "fred" / "通胀_通胀预期" / "PCE_同比.csv",
        "value_column": "value",
        "label": "PCE同比",
        "frequency_label": "月频",
    },
    "core_pce_yoy": {
        "path": ROOT / "data" / "fred" / "通胀_通胀预期" / "核心PCE_同比.csv",
        "value_column": "value",
        "label": "核心PCE同比",
        "frequency_label": "月频",
    },
    "michigan_1y_inflation_expectation": {
        "path": ROOT / "data" / "fred" / "通胀_通胀预期" / "密歇根大学1年通胀预期.csv",
        "value_column": "value",
        "label": "密歇根大学1年通胀预期",
        "frequency_label": "月频",
    },
    "broad_dollar": {
        "path": ROOT / "data" / "fred" / "汇率" / "美元广义贸易加权指数.csv",
        "value_column": "value",
        "label": "美元广义贸易加权指数",
        "frequency_label": "日频",
    },
    "eurusd": {
        "path": ROOT / "data" / "fx" / "EURUSD.csv",
        "value_column": "close",
        "label": "EUR/USD",
        "frequency_label": "日频",
    },
    "usdjpy": {
        "path": ROOT / "data" / "fx" / "USDJPY.csv",
        "value_column": "close",
        "label": "USD/JPY",
        "frequency_label": "日频",
    },
    "gbpusd": {
        "path": ROOT / "data" / "fx" / "GBPUSD.csv",
        "value_column": "close",
        "label": "GBP/USD",
        "frequency_label": "日频",
    },
    "audusd": {
        "path": ROOT / "data" / "fx" / "AUDUSD.csv",
        "value_column": "close",
        "label": "AUD/USD",
        "frequency_label": "日频",
    },
    "usdchf": {
        "path": ROOT / "data" / "fx" / "USDCHF.csv",
        "value_column": "close",
        "label": "USD/CHF",
        "frequency_label": "日频",
    },
    "vix": {
        "path": ROOT / "data" / "stock_volatility" / "VIX.csv",
        "value_column": "value",
        "label": "VIX",
        "frequency_label": "日频",
    },
    "vvix": {
        "path": ROOT / "data" / "stock_volatility" / "VVIX.csv",
        "value_column": "value",
        "label": "VVIX",
        "frequency_label": "日频",
    },
    "vxn": {
        "path": ROOT / "data" / "stock_volatility" / "VXN.csv",
        "value_column": "value",
        "label": "VXN",
        "frequency_label": "日频",
    },
    "vix3m": {
        "path": ROOT / "data" / "stock_volatility" / "VIX3M.csv",
        "value_column": "value",
        "label": "VIX3M",
        "frequency_label": "日频",
    },
    "skew": {
        "path": ROOT / "data" / "stock_volatility" / "SKEW.csv",
        "value_column": "value",
        "label": "SKEW",
        "frequency_label": "日频",
    },
    "stlfsi": {
        "path": ROOT / "data" / "fred" / "金融压力" / "圣路易斯金融压力指数.csv",
        "value_column": "value",
        "label": "圣路易斯金融压力指数",
        "frequency_label": "周频",
    },
    "hy_oas": {
        "path": ROOT / "data" / "fred" / "信用利差" / "高收益信用利差_OAS.csv",
        "value_column": "value",
        "label": "高收益信用利差 OAS",
        "frequency_label": "日频",
    },
    "ig_oas": {
        "path": ROOT / "data" / "fred" / "信用利差" / "投资级信用利差_OAS.csv",
        "value_column": "value",
        "label": "投资级信用利差 OAS",
        "frequency_label": "日频",
    },
    "copper": {
        "path": ROOT / "data" / "fred" / "工业金属" / "铜价.csv",
        "value_column": "value",
        "label": "铜价",
        "frequency_label": "月频",
    },
    "wti": {
        "path": ROOT / "data" / "fred" / "油价指标" / "WTI原油现货价.csv",
        "value_column": "value",
        "label": "WTI原油现货价",
        "frequency_label": "日频",
    },
    "total_debt_to_gdp": {
        "path": ROOT / "data" / "fred" / "债务_财政" / "Total Federal Debt to GDP.csv",
        "value_column": "value",
        "label": "联邦总债务 / GDP",
        "frequency_label": "季频",
    },
    "debt_held_by_public_to_gdp": {
        "path": ROOT / "data" / "fred" / "债务_财政" / "Federal Debt Held by Public to GDP.csv",
        "value_column": "value",
        "label": "公众持有联邦债务 / GDP",
        "frequency_label": "季频",
    },
    "interest_payments_to_gdp": {
        "path": ROOT / "data" / "fred" / "债务_财政" / "Federal Interest Payments to GDP.csv",
        "value_column": "value",
        "label": "联邦利息支出 / GDP",
        "frequency_label": "季频",
    },
    "average_interest_rate_on_debt": {
        "path": ROOT / "data" / "us_debt" / "Average Interest Rate on Total Interest-Bearing Debt.csv",
        "value_column": "value",
        "label": "平均付息成本",
        "frequency_label": "月频",
    },
    "marketable_debt_outstanding": {
        "path": ROOT / "data" / "us_debt" / "Marketable Treasury Securities Outstanding.csv",
        "value_column": "value",
        "label": "可流通美债余额",
        "frequency_label": "月频",
    },
    "treasury_borrowing_estimate": {
        "path": ROOT / "data" / "us_debt" / "Treasury Net Marketable Borrowing Estimate.csv",
        "value_column": "value",
        "label": "净可流通融资需求估计",
        "frequency_label": "季频",
    },
}

SERIES_DESCRIPTIONS_ZH = {
    "xau": "伦敦金现货的美元价格主序列，用来观察金价趋势本身。",
    "sp500": "标普500指数，代表美国大盘风险资产表现。",
    "nasdaq100": "纳斯达克100指数，代表成长和科技风险偏好。",
    "tips10y": "美国10年期TIPS实际收益率，是黄金最核心的机会成本指标之一。",
    "dxy": "美元对主要可兑换货币的狭义指数，用来观察美元强弱。",
    "nominal10y": "美国10年期国债名义收益率，反映长端无风险利率水平。",
    "breakeven10y": "美国10年期盈亏平衡通胀率，代表市场定价的中长期通胀预期。",
    "credit_oas_hy": "美国高收益信用利差，用来衡量信用风险和融资环境。",
    "sofr": "担保隔夜融资利率，反映美元短端资金价格。",
    "xau_monthly": "黄金月度收盘价，用来拉长视角观察中期趋势。",
    "gvz": "黄金波动率指数，反映期权市场对金价波动的预期。",
    "gld_holdings": "GLD黄金ETF总持仓，代表配置型资金是否持续回流。",
    "global_gold_etf_holdings_weekly": "全球实物黄金ETF周度总持仓，观察中期配置资金是否持续增配。",
    "gold_etf_flows": "全球黄金ETF月度净流量，用来观察资金申赎方向。",
    "global_gold_etf_flows_weekly": "全球黄金ETF周度净流量，更适合观察短期资金流拐点。",
    "gld_volume": "GLD日成交量，用来观察黄金ETF交易热度是否放大。",
    "global_gold_mine_production_quarterly": "全球矿产金季度产量，反映黄金供给端变化。",
    "global_gold_aisc_quarterly": "全球黄金矿商全维持成本，反映供给成本线和行业利润压力。",
    "official_gold_reserve_change_quarterly": "各国央行官方黄金储备季度变动，观察央行净购金或减持方向。",
    "tips5y": "美国5年期TIPS实际收益率，更偏中短期的实际利率信号。",
    "tips30y": "美国30年期TIPS实际收益率，用来看超长端实际利率约束。",
    "fedfunds": "联邦基金利率，代表美联储政策利率水平。",
    "tbill3m": "3个月美债收益率，代表短端名义利率和现金替代收益。",
    "m2": "美国M2货币供应量，用来观察广义流动性环境。",
    "breakeven5y": "美国5年期盈亏平衡通胀率，反映中短端通胀预期。",
    "forward5y5y": "5年期5年期远期通胀预期，反映更长期的通胀锚。",
    "cpi_yoy": "美国CPI同比，衡量居民消费价格的总体通胀。",
    "core_cpi_yoy": "美国核心CPI同比，剔除食品和能源后的核心通胀。",
    "pce_yoy": "美国PCE同比，是美联储常看的总通胀指标。",
    "core_pce_yoy": "美国核心PCE同比，是货币政策更关注的核心通胀指标。",
    "michigan_1y_inflation_expectation": "密歇根大学1年通胀预期，反映居民短期通胀感知和预期。",
    "broad_dollar": "美元广义贸易加权指数，比DXY覆盖更广的美元强弱口径。",
    "eurusd": "欧元兑美元汇率，是最重要的美元对手盘之一。",
    "usdjpy": "美元兑日元汇率，常用来区分套息和避险驱动。",
    "gbpusd": "英镑兑美元汇率，用来补充欧洲发达市场对美元的反馈。",
    "audusd": "澳元兑美元汇率，对全球增长和大宗商品周期更敏感。",
    "usdchf": "美元兑瑞郎汇率，可补充避险货币对美元的反应。",
    "vix": "标普500隐含波动率指数，代表市场风险厌恶程度。",
    "vvix": "VIX的波动率指数，用来观察波动率本身是否失稳。",
    "vxn": "纳斯达克100隐含波动率指数，用来观察科技成长风格的风险溢价。",
    "vix3m": "3个月期限的标普隐含波动率，用来区分短期恐慌和中期波动预期。",
    "skew": "标普尾部风险定价指数，反映市场是否在买入崩盘保护。",
    "stlfsi": "圣路易斯联储金融压力指数，衡量系统性金融压力。",
    "hy_oas": "美国高收益OAS利差，观察高风险信用融资环境。",
    "ig_oas": "美国投资级OAS利差，观察高质量信用融资环境。",
    "copper": "铜价常被用作全球工业需求和增长预期的温度计。",
    "wti": "WTI原油现货价格，反映能源成本和周期需求变化。",
    "total_debt_to_gdp": "美国联邦总债务占GDP比重，用来观察总杠杆压力。",
    "debt_held_by_public_to_gdp": "公众持有联邦债务占GDP比重，更接近市场实际吸收的债务规模。",
    "interest_payments_to_gdp": "联邦利息支出占GDP比重，反映债务利息负担。",
    "average_interest_rate_on_debt": "美国全部计息债务的平均付息成本，观察高利率如何向财政成本传导。",
    "marketable_debt_outstanding": "可流通美国国债余额，代表市场需要承接的存量供给。",
    "treasury_borrowing_estimate": "美国财政部净可流通融资需求估算，观察新增供给压力。",
}

TREND_THRESHOLDS = {
    "tips10y": 0.03,
    "nominal10y": 0.03,
    "breakeven10y": 0.03,
    "credit_oas_hy": 0.03,
    "sofr": 0.03,
    "dxy": 0.20,
    "vix": 0.50,
    "vxn": 0.50,
    "vix3m": 0.50,
    "skew": 1.00,
    "average_interest_rate_on_debt": 0.03,
    "tbill3m": 0.03,
    "michigan_1y_inflation_expectation": 0.10,
    "official_gold_reserve_change_quarterly": 10.0,
}

TAB_DEFINITIONS = [
    {"id": "overview", "label": "总览", "description": "当前判断"},
    {"id": "gold", "label": "黄金本体", "description": "价格与资金"},
    {"id": "rates", "label": "利率流动性", "description": "真实利率主线"},
    {"id": "inflation", "label": "通胀通胀预期", "description": "预期与兑现"},
    {"id": "usd", "label": "美元汇率", "description": "主指数与货币对"},
    {"id": "risk", "label": "风险信用", "description": "风险偏好与压力"},
    {"id": "fiscal", "label": "财政债务", "description": "存量与融资"},
]

TAB_LAYOUTS = {
    "overview": {
        "hero_chart_ids": ["xau", "sp500", "nasdaq100"],
        "detail_chart_ids": ["tips10y", "dxy", "nominal10y", "breakeven10y", "credit_oas_hy", "sofr"],
        "summary_cards": ["gold_summary", "rates_summary", "inflation_summary"],
    },
    "gold": {
        "title": "黄金本体",
        "description": "把黄金从结果变量拆出来，单独看价格、波动、资金、供给和央行配置。",
        "sections": [
            {
                "title": "价格与波动",
                "description": "先判断金价趋势本身，再区分趋势和波动是否同步放大。",
                "series_ids": ["xau", "xau_monthly", "gvz"],
            },
            {
                "title": "ETF资金流",
                "description": "把持仓、周度申赎和交易热度放在一起，看配置资金是否真正回流。",
                "series_ids": [
                    "gld_holdings",
                    "global_gold_etf_holdings_weekly",
                    "gold_etf_flows",
                    "global_gold_etf_flows_weekly",
                    "gld_volume",
                ],
            },
            {
                "title": "供给与央行",
                "description": "用矿产金供给、成本线和央行购金，补齐黄金长期基本面。",
                "series_ids": [
                    "global_gold_mine_production_quarterly",
                    "global_gold_aisc_quarterly",
                    "official_gold_reserve_change_quarterly",
                ],
            },
        ],
    },
    "rates": {
        "title": "利率 / 流动性",
        "description": "看黄金最核心的驱动页：实际利率、名义利率与短端流动性。",
        "sections": [
            {
                "title": "实际利率期限层级",
                "description": "优先看5Y、10Y、30Y TIPS是否共振。",
                "series_ids": ["tips10y", "tips5y", "tips30y"],
            },
            {
                "title": "短端利率与货币环境",
                "description": "用SOFR、联邦基金、3个月美债和M2看短端约束是否放松。",
                "series_ids": ["sofr", "fedfunds", "tbill3m", "m2"],
            },
        ],
    },
    "inflation": {
        "title": "通胀 / 通胀预期",
        "description": "把市场定价的通胀预期和已经实现的通胀分开展示。",
        "sections": [
            {
                "title": "市场预期",
                "description": "先看市场交易出来的通胀补偿与远期预期。",
                "series_ids": ["breakeven10y", "breakeven5y", "forward5y5y"],
            },
            {
                "title": "已实现通胀",
                "description": "再看CPI、PCE和居民调查是否在验证市场叙事。",
                "series_ids": [
                    "cpi_yoy",
                    "core_cpi_yoy",
                    "pce_yoy",
                    "core_pce_yoy",
                    "michigan_1y_inflation_expectation",
                ],
            },
        ],
    },
    "usd": {
        "title": "美元 / 汇率",
        "description": "用DXY、广义美元和核心货币对拆解美元强弱。",
        "insights": [
            {
                "key": "usd_direction",
                "label": "美元总方向",
                "series_id": "dxy",
                "up_text": "美元走强",
                "down_text": "美元走弱",
                "flat_text": "美元横盘",
                "up_tone": "negative",
                "down_tone": "positive",
                "flat_tone": "neutral",
            },
            {
                "key": "broad_dollar",
                "label": "广义美元",
                "series_id": "broad_dollar",
                "up_text": "贸易加权抬升",
                "down_text": "贸易加权回落",
                "flat_text": "广义美元横盘",
                "up_tone": "negative",
                "down_tone": "positive",
                "flat_tone": "neutral",
            },
            {
                "key": "eurusd",
                "label": "欧元对美元",
                "series_id": "eurusd",
                "up_text": "欧元走强，美元回落",
                "down_text": "欧元走弱，美元偏强",
                "flat_text": "欧元横盘",
                "up_tone": "positive",
                "down_tone": "negative",
                "flat_tone": "neutral",
            },
        ],
        "sections": [
            {
                "title": "美元主指数",
                "description": "先看美元总方向，再判断是狭义美元走强还是更广泛的美元收紧。",
                "series_ids": ["dxy", "broad_dollar", "eurusd"],
            },
            {
                "title": "主要货币对",
                "description": "补上日元、英镑、澳元和瑞郎，区分增长、避险与套息驱动。",
                "series_ids": ["usdjpy", "gbpusd", "audusd", "usdchf"],
            },
        ],
    },
    "risk": {
        "title": "风险偏好 / 信用",
        "description": "区分黄金上涨到底是宽松友好，还是风险防御。",
        "insights": [
            {
                "key": "risk_assets",
                "label": "风险资产",
                "series_id": "sp500",
                "up_text": "风险资产修复",
                "down_text": "风险资产回撤",
                "flat_text": "风险资产横盘",
                "up_tone": "positive",
                "down_tone": "negative",
                "flat_tone": "neutral",
            },
            {
                "key": "vix_state",
                "label": "波动率",
                "series_id": "vix",
                "up_text": "波动率抬升",
                "down_text": "波动率回落",
                "flat_text": "波动率横盘",
                "up_tone": "negative",
                "down_tone": "positive",
                "flat_tone": "neutral",
            },
            {
                "key": "stress_state",
                "label": "金融压力",
                "series_id": "stlfsi",
                "up_text": "压力升温",
                "down_text": "压力缓和",
                "flat_text": "压力平稳",
                "up_tone": "negative",
                "down_tone": "positive",
                "flat_tone": "neutral",
            },
        ],
        "sections": [
            {
                "title": "股指与波动率",
                "description": "先看风险资产方向，再看大盘和科技波动率是否同步升温。",
                "series_ids": ["sp500", "nasdaq100", "vix", "vxn"],
            },
            {
                "title": "信用与尾部风险",
                "description": "把信用利差、期限波动率和尾部保护需求放在一起看系统压力。",
                "series_ids": ["hy_oas", "ig_oas", "vvix", "vix3m", "skew", "stlfsi", "copper", "wti"],
            },
        ],
    },
    "fiscal": {
        "title": "财政 / 债务",
        "description": "这一页偏中长期，主要看债务存量、利息负担和融资需求。",
        "insights": [
            {
                "key": "debt_ratio",
                "label": "债务率",
                "series_id": "total_debt_to_gdp",
                "up_text": "债务率抬升",
                "down_text": "债务率回落",
                "flat_text": "债务率横盘",
                "up_tone": "negative",
                "down_tone": "positive",
                "flat_tone": "neutral",
            },
            {
                "key": "interest_burden",
                "label": "利息负担",
                "series_id": "interest_payments_to_gdp",
                "up_text": "利息负担上升",
                "down_text": "利息负担缓和",
                "flat_text": "利息负担平稳",
                "up_tone": "negative",
                "down_tone": "positive",
                "flat_tone": "neutral",
            },
            {
                "key": "treasury_supply",
                "label": "融资需求",
                "series_id": "treasury_borrowing_estimate",
                "up_text": "融资需求走高",
                "down_text": "融资需求回落",
                "flat_text": "融资需求平稳",
                "up_tone": "negative",
                "down_tone": "positive",
                "flat_tone": "neutral",
            },
        ],
        "sections": [
            {
                "title": "债务压力",
                "description": "先看债务率、利息支出和平均付息成本是否持续抬升。",
                "series_ids": [
                    "total_debt_to_gdp",
                    "debt_held_by_public_to_gdp",
                    "interest_payments_to_gdp",
                    "average_interest_rate_on_debt",
                ],
            },
            {
                "title": "融资与供给",
                "description": "再看市场需要吸收多少新增国债供给。",
                "series_ids": ["marketable_debt_outstanding", "treasury_borrowing_estimate"],
            },
        ],
    },
}


def compute_trend_label(series_id: str, start_value: float, end_value: float) -> str:
    delta = end_value - start_value
    threshold = TREND_THRESHOLDS.get(series_id, 0.0)
    if abs(delta) < threshold:
        return "横盘"
    return "上升" if delta > 0 else "下降"


def load_series_frame(path: Path, value_column: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    normalized = frame.loc[:, ["date", value_column]].rename(columns={value_column: "value"}).copy()
    normalized["date"] = pd.to_datetime(normalized["date"], utc=False).dt.strftime("%Y-%m-%d")
    normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")
    normalized = normalized.dropna(subset=["date", "value"]).sort_values("date").reset_index(drop=True)
    return normalized


def build_dashboard_payload() -> dict:
    series = {}
    all_dates: list[str] = []
    series_order = ["xau", "sp500", "nasdaq100", "tips10y", "dxy", "nominal10y", "breakeven10y", "credit_oas_hy", "sofr"]

    for series_id, spec in DASHBOARD_SERIES.items():
        frame = load_series_frame(spec["path"], spec["value_column"])
        points = frame.to_dict(orient="records")
        series[series_id] = {
            "label": spec["label"],
            "points": points,
            "value_precision": 2,
            "frequency_label": spec["frequency_label"],
            "description_zh": SERIES_DESCRIPTIONS_ZH[series_id],
            "latest_date": points[-1]["date"] if points else None,
        }
        all_dates.extend(point["date"] for point in points)

    unique_dates = sorted(set(all_dates))
    default_start_index = max(len(unique_dates) - 252, 0)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "title": "黄金 / 美元 / 利率 信号矩阵",
            "hero_chart_ids": TAB_LAYOUTS["overview"]["hero_chart_ids"],
            "detail_chart_ids": TAB_LAYOUTS["overview"]["detail_chart_ids"],
            "series_order": series_order,
            "tab_order": [tab["id"] for tab in TAB_DEFINITIONS],
            "tabs": TAB_DEFINITIONS,
            "quadrant_axes": {"x": "dxy", "y": "tips10y"},
            "default_range": {
                "start": unique_dates[default_start_index],
                "end": unique_dates[-1],
            },
            "trend_thresholds": TREND_THRESHOLDS,
        },
        "series": series,
        "tab_layouts": TAB_LAYOUTS,
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build_dashboard_payload(), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
