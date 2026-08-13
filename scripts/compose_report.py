#!/usr/bin/env python3
"""Compose a building big-data report by orchestrating the building MCP.

Calls the upstream building-mcp-server tools and assembles a structured JSON
payload rendered into a professional HTML / Markdown report. Supports
``--dry-run`` which returns a well-formed skeleton from the bundled sample data
WITHOUT contacting the MCP.

Two analysis modes:
  - Enterprise mode (default, ``--enterprise``): office address details, office
    address stats, plus the building detail query for the host building.
  - Market search mode (``--address`` / ``--property-type``): query building
    inventory in a region / property type without an enterprise subject.

This file never prints secrets; MCP credentials live in the server's own .env.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
from typing import Any, Dict, List, Mapping, Optional

from common import REPORT_BANNER, REPORT_TYPE, json_dumps, load_json_file, print_json
import mcp_client
from render_report import render_html, render_markdown, html_to_pdf

SAMPLE_PATH = pathlib.Path(__file__).resolve().parent.parent / "assets" / "report.example.json"

# Building MCP tools.
T_FUZZY = "building_bigdata_fuzzy_search"
T_OFFICE_DETAILS = "building_bigdata_office_address_details"
T_OFFICE_STATS = "building_bigdata_office_address_stats"
T_BUILDING_QUERY = "building_bigdata_building_query"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _is_api_error(value: Any) -> bool:
    """Detect MCP API error responses (not empty data, but actual failures like 405)."""
    if value is None:
        return False
    if isinstance(value, str):
        return any(s in value for s in ("接口调用失败", "查询失败", "状态码：4", "状态码：5"))
    if isinstance(value, dict):
        for v in value.values():
            if isinstance(v, str) and any(s in v for s in ("接口调用失败", "查询失败", "状态码：4", "状态码：5")):
                return True
    return False

def _first_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if _is_api_error(value):
            return []
        for key in ("resultList", "list", "items", "data"):
            if isinstance(value.get(key), list):
                return value[key]
    if value in (None, "", {}):
        return []
    return [value]


def _first_record(value: Any) -> Dict[str, Any]:
    for record in _first_list(value):
        if isinstance(record, dict):
            return record
    if isinstance(value, dict):
        return value
    return {}


def _text(value: Any, limit: int = 0) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        t = json.dumps(value, ensure_ascii=False)
    else:
        t = str(value)
    t = " ".join(t.split())
    if limit and len(t) > limit:
        return t[: limit - 1].rstrip() + "…"
    return t


def _int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_call(tool: str, arguments: Dict[str, Any]) -> Any:
    try:
        result = mcp_client.call_tool(tool, arguments)
        # Detect API error responses (405, etc.) and return error marker
        if _is_api_error(result):
            return {"_error": "API错误", "_raw": result}
        return result
    except Exception as exc:
        return {"_error": str(exc)}


def _safe_total(payload: Any) -> Any:
    if isinstance(payload, dict):
        if _is_api_error(payload):
            return None
        return payload.get("total")
    return None


def _format_capital(val: Any, coin: str = "") -> str:
    """Format capital value: 10995210218.0 → '109.95 亿'."""
    try:
        v = float(val)
        if v >= 1e8:
            s = f"{v / 1e8:.2f} 亿"
        elif v >= 1e4:
            s = f"{v / 1e4:.2f} 万"
        else:
            s = f"{v:.0f}"
        if coin:
            s += f" {coin}"
        return s
    except (TypeError, ValueError):
        return _text(val) if val else "-"


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #

def resolve_enterprise_name(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {"keyword": "", "enterprise": "", "resolved": False, "reason": "关键词为空"}
    if any(suffix in raw for suffix in ("公司", "集团", "有限", "院", "厂", "中心", "事务所", "合作社", "合伙")):
        return {"keyword": raw, "enterprise": raw, "resolved": True, "reason": "视为企业全称"}
    fuzzy = _safe_call(T_FUZZY, {"matchKeyword": raw, "pageSize": 1})
    record = _first_record(fuzzy)
    name = str(record.get("name") or "").strip()
    if name:
        profile = _extract_profile(record)
        return {"keyword": raw, "enterprise": name, "resolved": True, "reason": "由关键词模糊查询补全", "fuzzy_total": _int(_safe_total(fuzzy)), "profile": profile}
    return {"keyword": raw, "enterprise": raw, "resolved": False, "reason": "模糊查询未命中企业全称，按关键词直查"}


def _extract_profile(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract enterprise profile fields from a fuzzy_search record."""
    return {
        "name": _text(record.get("name")),
        "reg_capital": record.get("regCapitalValue"),
        "reg_capital_coin": _text(record.get("regCapitalCoinType")),
        "annual_turnover": _text(record.get("annualTurnover")),
        "oper_status": _text(record.get("operStatus")),
        "enterprise_type": _text(record.get("enterpriseType")),
        "found_time": _text(record.get("foundTime")),
        "legal_rep": _text(record.get("legalRepresentative")),
        "address": _text(record.get("address")),
        "homepage": _text(record.get("homepage")),
    }


# --------------------------------------------------------------------------- #
# Section builders
# --------------------------------------------------------------------------- #

def build_subject(raw: str, resolved: Mapping[str, Any], keyword_type: str) -> Dict[str, Any]:
    return {
        "enterprise": resolved.get("enterprise") or raw,
        "matchKeyword": resolved.get("enterprise") or raw,
        "keywordType": keyword_type,
        "match_raw": raw,
        "resolved": bool(resolved.get("resolved")),
        "resolve_reason": resolved.get("reason", ""),
    }


def build_caliber(subject: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "match_target": subject.get("enterprise") or subject.get("match_raw"),
        "match_type": f"楼宇/办公地址数据按企业主体匹配（keywordType={subject.get('keywordType', 'name')}）；楼宇查询支持按地区/楼宇类型/关键词检索",
        "data_scope": "企业办公地址详情、办公地址分布统计（城市/省份/入驻方式/来源）、楼宇查询明细",
        "products": ["企业办公地址详情", "企业办公地址统计", "楼宇查询"],
        "limit": "数据来自楼宇/办公公开数据源；少量字段可能存在更新延迟。",
    }


def build_metrics(details: Any, stats: Any, building: Any, profile: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
    metrics: List[Dict[str, Any]] = []
    d_total = _int(_safe_total(details)) if isinstance(details, dict) else None
    s = stats if isinstance(stats, dict) else {}
    city_list = s.get("officeCityStats") if isinstance(s.get("officeCityStats"), list) else []
    city_count = len(city_list) if isinstance(city_list, list) else None
    b_total = _int(_safe_total(building)) if isinstance(building, dict) else None

    # --- Office address metrics ---
    metrics.append({"label": "办公地址总数", "value": (_text(d_total) if d_total is not None else "-"), "hint": "企业办公地址总数"})
    if city_count and d_total:
        metrics.append({"label": "覆盖城市数", "value": _text(city_count), "hint": "办公地址所涉城市数", "delta": f"地均 {d_total / city_count:.1f} 个/城"})
    elif city_count:
        metrics.append({"label": "覆盖城市数", "value": _text(city_count), "hint": "办公地址所涉城市数"})

    # Province count (derived)
    province_rows = _office_province_rows(details)
    if province_rows:
        metrics.append({"label": "覆盖省份数", "value": str(len(province_rows)), "hint": "办公地址所涉省份数"})

    # CR3 city concentration
    stat_rows = _office_stat_rows(stats)
    if stat_rows:
        conc = _concentration(stat_rows, "城市", "办公地址数量", 3)
        if conc:
            metrics.append({"label": "CR3城市集中度", "value": f"{conc['cr']:.0f}%", "hint": f"前3城市合计，TOP1：{conc['top']}"})

    # --- Building metrics ---
    if b_total is not None:
        metrics.append({"label": "楼宇库存量", "value": _text(b_total), "hint": "查询命中楼盘数"})

    # --- Enterprise profile metrics ---
    if profile:
        if profile.get("reg_capital"):
            metrics.append({"label": "注册资本", "value": _format_capital(profile["reg_capital"], profile.get("reg_capital_coin", "")), "hint": "企业注册资本"})
        if profile.get("annual_turnover"):
            metrics.append({"label": "年营业额", "value": profile["annual_turnover"], "hint": "企业年营业额"})
        if profile.get("found_time"):
            year = profile["found_time"][:4] if len(profile["found_time"]) >= 4 else profile["found_time"]
            metrics.append({"label": "成立年份", "value": year, "hint": f"成立于 {profile['found_time']}"})
        if profile.get("oper_status"):
            metrics.append({"label": "经营状态", "value": profile["oper_status"], "hint": "企业经营状态"})

    return [m for m in metrics if m.get("value") not in ("", None, "-")]


def _address_value(value: Any) -> str:
    """officeAddress/estateAddress may be a dict {province,city,district,value}
    or a plain string. Extract the human-readable value."""
    if isinstance(value, dict):
        return _text(value.get("value")) or _region_text(value)
    return _text(value)


def _address_province(value: Any) -> str:
    """Extract province from an address dict (empty string if not a dict)."""
    if isinstance(value, dict):
        return _text(value.get("province"))
    return ""


def _address_city(value: Any) -> str:
    """Extract city from an address dict."""
    if isinstance(value, dict):
        return _text(value.get("city"))
    return ""


def _address_district(value: Any) -> str:
    """Extract district from an address dict."""
    if isinstance(value, dict):
        return _text(value.get("district"))
    return ""


def _region_text(value: Any) -> str:
    """Render an address dict {province,city,district} as 省/市/区."""
    if isinstance(value, dict):
        parts = [value.get(k) for k in ("province", "city", "district") if value.get(k)]
        return "、".join(str(p).strip() for p in parts if str(p).strip())
    return _text(value)


# Source type display mapping
_SOURCE_MAP = {
    "enterprise": "工商登记",
    "office": "办公地址",
    "recruiting": "招聘信息",
}


def _office_detail_rows(details: Any) -> List[Dict[str, Any]]:
    out = []
    for item in _first_list(details):
        if not isinstance(item, dict):
            continue
        addr = item.get("officeAddress", {})
        out.append({
            "办公地址": _address_value(addr) or "-",
            "所在城市": _address_city(addr) or "-",
            "所在区域": _address_district(addr) or "-",
            "所在楼宇": _text(item.get("estateName")) or "-",
            "入驻方式": _text(item.get("officeSettleType")) or "-",
            "地址来源": _SOURCE_MAP.get(_text(item.get("officeSourceType")), _text(item.get("officeSourceType"))) or "-",
        })
    return out


def _office_stat_rows(stats: Any) -> List[Dict[str, Any]]:
    out = []
    for item in _first_list(stats.get("officeCityStats") if isinstance(stats, dict) else stats):
        if not isinstance(item, dict):
            continue
        out.append({
            "城市": _text(item.get("city")) or "-",
            "办公地址数量": _text(item.get("count") or item.get("value") or "-"),
        })
    return out


def _building_rows(building: Any) -> List[Dict[str, Any]]:
    out = []
    for item in _first_list(building):
        if not isinstance(item, dict):
            continue
        out.append({
            "楼宇名称": _text(item.get("estateName")) or "-",
            "楼宇类型": _text(item.get("estatePropertyType")) or "-",
            "楼宇地址": _address_value(item.get("estateAddress")) or "-",
            "入驻企业数": _text(item.get("estateEnterpriseCount") or "-"),
        })
    return out


def _building_type_rows(building_rows: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate building_query rows by 楼宇类型 into a {类型,数量} distribution."""
    counts: Dict[str, int] = {}
    for r in building_rows:
        t = (r.get("楼宇类型") or "-").strip()
        if not t:
            t = "-"
        counts[t] = counts.get(t, 0) + 1
    return [{"楼宇类型": k, "数量": str(v)} for k, v in counts.items()]


def _office_province_rows(details: Any) -> List[Dict[str, Any]]:
    """Aggregate office records by province into a {省份,办公点数} distribution."""
    counts: Dict[str, int] = {}
    for item in _first_list(details):
        if not isinstance(item, dict):
            continue
        prov = _address_province(item.get("officeAddress")).strip()
        if not prov:
            continue
        counts[prov] = counts.get(prov, 0) + 1
    return [{"省份": k, "办公点数": str(v)} for k, v in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)]


def _office_settle_type_rows(details: Any) -> List[Dict[str, Any]]:
    """Aggregate by 入驻方式 (officeSettleType) into a {入驻方式,数量} distribution."""
    counts: Dict[str, int] = {}
    for item in _first_list(details):
        if not isinstance(item, dict):
            continue
        t = _text(item.get("officeSettleType")).strip() or "未知"
        counts[t] = counts.get(t, 0) + 1
    return [{"入驻方式": k, "数量": str(v)} for k, v in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)]


def _office_source_type_rows(details: Any) -> List[Dict[str, Any]]:
    """Aggregate by 地址来源 (officeSourceType) into a {地址来源,数量} distribution."""
    counts: Dict[str, int] = {}
    for item in _first_list(details):
        if not isinstance(item, dict):
            continue
        raw = _text(item.get("officeSourceType")).strip()
        t = _SOURCE_MAP.get(raw, raw) or "其他"
        counts[t] = counts.get(t, 0) + 1
    return [{"地址来源": k, "数量": str(v)} for k, v in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)]


def _concentration(rows: List[Mapping[str, Any]], name_key: str, value_key: str, top_n: int = 3) -> Dict[str, Any]:
    """Compute top-N concentration (CRn) and dominant category from {name,count} rows."""
    items = []
    for r in rows:
        try:
            items.append((r.get(name_key, "-"), float(str(r.get(value_key, 0)).replace(",", ""))))
        except (TypeError, ValueError):
            items.append((r.get(name_key, "-"), 0.0))
    total = sum(v for _, v in items)
    if not total:
        return {}
    items.sort(key=lambda x: x[1], reverse=True)
    cr = sum(v for _, v in items[:top_n]) / total * 100
    return {"top": items[0][0], "top_share": items[0][1] / total * 100, "cr": cr, "total": total, "n": len(items)}


def build_core_analysis(details: Any, stats: Any, building: Any) -> Dict[str, Any]:
    detail_rows = _office_detail_rows(details)
    stat_rows = _office_stat_rows(stats)
    building_rows = _building_rows(building)
    building_type_rows = _building_type_rows(building_rows)
    office_province_rows = _office_province_rows(details)
    settle_type_rows = _office_settle_type_rows(details)
    source_type_rows = _office_source_type_rows(details)

    sections = [
        {"key": "office_details", "title": "办公地址详情", "kind": "table",
         "note": f"共 {_safe_total(details) if isinstance(details, dict) and _safe_total(details) is not None else '若干'} 条办公地址记录，展示前若干条",
         "columns": [("办公地址", "办公地址"), ("所在城市", "所在城市"), ("所在区域", "所在区域"), ("所在楼宇", "所在楼宇"), ("入驻方式", "入驻方式"), ("地址来源", "地址来源")]},
        {"key": "office_province", "title": "办公地址省份分布", "kind": "bar",
         "note": "按办公地址所在省份聚合办公点数量",
         "chart": {"name": "省份", "value": "办公点数", "orient": "h"},
         "columns": [("省份", "省份"), ("办公点数", "办公点数")]},
        {"key": "office_stats", "title": "办公地址城市分布", "kind": "donut", "note": "按城市统计办公地址数量",
         "chart": {"name": "城市", "value": "办公地址数量"},
         "columns": [("城市", "城市"), ("办公地址数量", "办公地址数量")]},
        {"key": "settle_type", "title": "入驻方式分布", "kind": "donut", "note": "按入驻方式（工商注册入驻 / 办公地址入驻）统计",
         "chart": {"name": "入驻方式", "value": "数量"},
         "columns": [("入驻方式", "入驻方式"), ("数量", "数量")]},
        {"key": "source_type", "title": "地址来源分布", "kind": "donut", "note": "按地址来源类型（工商登记 / 办公地址 / 招聘信息）统计",
         "chart": {"name": "地址来源", "value": "数量"},
         "columns": [("地址来源", "地址来源"), ("数量", "数量")]},
        {"key": "building_query", "title": "楼宇查询明细", "kind": "table",
         "note": f"共 {_safe_total(building) if isinstance(building, dict) and _safe_total(building) is not None else '若干'} 个楼盘，展示前 N 个",
         "columns": [("楼宇名称", "楼宇名称"), ("楼宇类型", "楼宇类型"), ("楼宇地址", "楼宇地址"), ("入驻企业数", "入驻企业数")]},
        {"key": "building_type", "title": "楼宇类型分布", "kind": "bar", "note": "按楼宇类型聚合命中楼盘数量",
         "chart": {"name": "楼宇类型", "value": "数量", "orient": "h"},
         "columns": [("楼宇类型", "楼宇类型"), ("数量", "数量")]},
    ]

    return {
        "sections": sections,
        "office_details": detail_rows,
        "office_province": office_province_rows,
        "office_stats": stat_rows,
        "settle_type": settle_type_rows,
        "source_type": source_type_rows,
        "building_query": building_rows,
        "building_type": building_type_rows,
    }


def build_records(core: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for item in core.get("office_details") or []:
        out.append({
            "办公地址": item.get("办公地址") or "-",
            "所在楼宇": item.get("所在楼宇") or "-",
            "入驻方式": item.get("入驻方式") or "-",
            "地址来源": item.get("地址来源") or "-",
        })
    return out[:20]


def build_insights(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: List[Mapping[str, Any]], profile: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
    insights: List[Dict[str, Any]] = []
    metric_map = {m["label"]: str(m["value"]) for m in metrics}
    addr_total = metric_map.get("办公地址总数")
    city_count = metric_map.get("覆盖城市数")
    building_total = metric_map.get("楼宇库存量")

    # 1. Office address scale
    if addr_total:
        try:
            addr_n = float(addr_total)
            extra = ""
            if city_count:
                try:
                    cc = float(city_count)
                    if cc > 0:
                        extra = f"，地均 {addr_n / cc:.1f} 个/城市"
                except (TypeError, ValueError):
                    pass
        except (TypeError, ValueError):
            extra = ""
        insights.append({
            "feature": "办公地址规模",
            "evidence": f"企业办公地址总数 {addr_total}{extra}。",
            "interpretation": "办公地址总数反映企业实际经营网络的覆盖密度；多地址常见于分支机构、研发中心或区域销售据点，地均密度越高意味着单城集中度越深。",
        })

    # 2. City concentration
    stat_rows = core.get("office_stats") or []
    if stat_rows:
        conc = _concentration(stat_rows, "城市", "办公地址数量", 3)
        if conc:
            insights.append({
                "feature": "城市分布集中度",
                "evidence": f"“{conc['top']}”办公地址占比约 {conc['top_share']:.0f}%，前 3 城市合计 {conc['cr']:.0f}%（CR3）。",
                "interpretation": "城市集中度反映区域布局战略：CR3 偏高意味着以总部/核心城市为主、便于集中管控；CR3 偏低则代表分散布局、利于多区域市场渗透。",
            })

    # 3. Province concentration
    province_rows = core.get("office_province") or []
    if province_rows:
        conc = _concentration(province_rows, "省份", "办公点数", 3)
        if conc and conc.get("n", 0) > 1:
            insights.append({
                "feature": "省份分布集中度",
                "evidence": f"“{conc['top']}”办公地址占比约 {conc['top_share']:.0f}%，覆盖 {conc['n']} 个省份，前 3 省合计 {conc['cr']:.0f}%（CR3）。",
                "interpretation": "省份集中度反映企业区域战略重心：集中在少数省份意味着深耕核心市场，分散布局则利于全国拓展。省份数量越多，企业的区域辐射能力越强。",
            })

    # 4. Settle type structure
    settle_rows = core.get("settle_type") or []
    if settle_rows:
        total_settle = sum(int(r.get("数量", 0)) for r in settle_rows)
        if total_settle:
            top_settle = settle_rows[0].get("入驻方式", "")
            top_count = int(settle_rows[0].get("数量", 0))
            top_pct = top_count / total_settle * 100
            insights.append({
                "feature": "入驻方式结构",
                "evidence": f"“{top_settle}”占比约 {top_pct:.0f}%（{top_count}/{total_settle}）。",
                "interpretation": "工商注册入驻意味着该地址为法定注册地，办公地址入驻则为实际经营场所；两者比例反映企业的注册地与实际办公地的一致性。",
            })

    # 5. Source type structure
    source_rows = core.get("source_type") or []
    if source_rows and len(source_rows) > 1:
        total_source = sum(int(r.get("数量", 0)) for r in source_rows)
        if total_source:
            top_source = source_rows[0].get("地址来源", "")
            top_count = int(source_rows[0].get("数量", 0))
            top_pct = top_count / total_source * 100
            insights.append({
                "feature": "地址来源多样性",
                "evidence": f"地址来源覆盖 {len(source_rows)} 种渠道，“{top_source}”占比约 {top_pct:.0f}%。",
                "interpretation": "多来源地址意味着企业在工商登记、办公点、招聘等渠道均有露出，数据交叉验证度高；单一来源则覆盖面有限。",
            })

    # 6. Building enterprise density
    building_rows = core.get("building_query") or []
    if building_rows:
        try:
            ent_vals = [float(str(r.get("入驻企业数", "0")).replace(",", "")) for r in building_rows if r.get("入驻企业数") and str(r.get("入驻企业数")).replace(",", "").replace(".", "").isdigit()]
            if ent_vals:
                avg_ent = sum(ent_vals) / len(ent_vals)
                insights.append({
                    "feature": "楼宇承载密度",
                    "evidence": f"命中 {len(building_rows)} 个楼盘，单楼入驻企业均值约 {avg_ent:.0f} 家。",
                    "interpretation": "楼宇入驻密度反映目标区域写字楼/产业园的成熟度与集聚效应，是选址与招商评估供给质量的关键参考。",
                })
        except (TypeError, ValueError):
            pass

    # 7. Building type structure
    type_rows = core.get("building_type") or []
    if type_rows:
        conc = _concentration(type_rows, "楼宇类型", "数量", 2)
        if conc and conc.get("total", 0) > 1:
            insights.append({
                "feature": "楼宇类型结构",
                "evidence": f"“{conc['top']}”类楼盘占比约 {conc['top_share']:.0f}%。",
                "interpretation": "楼宇类型结构反映目标区域业态供给：写字楼偏多适合总部办公，产业园/综合体偏多适合产研一体化布局。",
            })

    # 8. Building stock reference
    if building_total and not building_rows:
        insights.append({
            "feature": "楼宇库存参考",
            "evidence": f"查询命中 {building_total} 个楼盘。",
            "interpretation": "楼盘库存量用于评估目标区域的写字楼/产业园供给与竞争格局，可辅助选址与招商决策。",
        })

    # 9. Enterprise profile overview
    if profile:
        parts = []
        if profile.get("reg_capital"):
            parts.append(f"注册资本 {_format_capital(profile['reg_capital'])}")
        if profile.get("found_time"):
            parts.append(f"成立于 {profile['found_time'][:4]} 年")
        if profile.get("annual_turnover"):
            parts.append(f"年营业额 {profile['annual_turnover']}")
        if profile.get("enterprise_type"):
            parts.append(f"企业类型 {profile['enterprise_type']}")
        if len(parts) >= 2:
            insights.append({
                "feature": "企业背景概况",
                "evidence": "、".join(parts) + "。",
                "interpretation": "企业注册资本与成立年限反映其规模与历史积淀，是评估合作稳定性的基础参考；营业额则体现当前经营体量。",
            })

    if not insights:
        insights.append({
            "feature": "数据完整性",
            "evidence": "部分维度未返回有效数据。",
            "interpretation": "建议核对匹配关键词是否为企业全称，或检查 MCP 连接与上游数据产品覆盖范围。",
        })
    return insights


def build_abstract(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: List[Mapping[str, Any]], profile: Optional[Mapping[str, Any]] = None) -> str:
    name = subject.get("enterprise") or subject.get("match_raw") or "目标企业"
    parts = [f"本报告以“{name}”为分析对象，基于楼宇/办公地址大数据，系统呈现企业办公地址详情、地址分布统计（城市/省份/入驻方式/来源）与楼宇查询明细。"]
    if metrics:
        kv = "、".join(f"{m['label']} {m['value']}" for m in metrics[:5])
        parts.append(f"关键指标包括：{kv}。")
    parts.append("报告同时给出办公地址规模、城市分布广度、入驻方式结构与楼宇库存的多维度解读，便于选址招商、市场分析与竞争格局研究参考。")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Dry-run sample
# --------------------------------------------------------------------------- #

def build_dry_run_payload(raw: str, keyword_type: str) -> Dict[str, Any]:
    try:
        sample = load_json_file(SAMPLE_PATH)
    except Exception:
        sample = {}
    sample = sample if isinstance(sample, dict) else {}
    subject = sample.get("subject") or {"enterprise": raw, "matchKeyword": raw, "keywordType": keyword_type, "match_raw": raw}
    subject = {**subject, "match_raw": raw, "keywordType": keyword_type}
    core = sample.get("core_analysis") or {}
    metrics = sample.get("metrics") or []
    return _assemble(subject, core, metrics, dry_run=True)


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def _assemble(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: List[Mapping[str, Any]], *, dry_run: bool, profile: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    abstract = build_abstract(subject, core, metrics, profile)
    records = build_records(core)
    insights = build_insights(subject, core, metrics, profile)
    # Quality gate: count populated core-analysis sections.
    ca = core if isinstance(core, dict) else {}
    secs = ca.get("sections", [])
    if secs:
        total_secs = len(secs)
        populated = sum(1 for s in secs if isinstance(s, dict) and ca.get(s.get("key")) not in (None, "", [], {}))
    else:
        total_secs = max(1, len([k for k in ca if k != "sections"]))
        populated = sum(1 for k in ca if k != "sections" and ca.get(k) not in (None, "", [], {}))
    quality_report = {
        "total_sections": total_secs,
        "populated_sections": populated,
        "empty_sections": total_secs - populated,
        "coverage_pct": round(populated / max(1, total_secs) * 100),
    }
    if populated == 0:
        print("⚠️ 质量门禁警告: 所有核心分析维度均无数据", file=sys.stderr)
    title = f"{subject.get('enterprise') or '目标企业'} 楼宇大数据报告"
    return {
        "report_type": REPORT_TYPE,
        "title": title,
        "banner": REPORT_BANNER,
        "subject": dict(subject),
        "abstract": abstract,
        "summary": abstract,
        "executive_summary": [item["interpretation"] for item in insights][:5] or [abstract[:120]],
        "metrics": list(metrics),
        "caliber": build_caliber(subject),
        "core_analysis": dict(core),
        "representative_records": records,
        "insights": insights,
        "data_source": {
            "mcp_server": "building-mcp-server",
            "products": [
                {"name": "企业办公地址详情", "product_id": "6786528b1677add9f934358f"},
                {"name": "企业办公地址统计", "product_id": "6786528b1677add9f934359d"},
                {"name": "楼宇查询", "product_id": "6786528b1677add9f93435db"},
            ],
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "dry_run": dry_run,
            "quality_report": quality_report,
        },
    }


def _query_buildings_for_estates(details: Any, page_size: int = 10) -> Any:
    """Query building metadata for the estate names found in office details.
    Falls back to returning empty if no estate names available."""
    estate_names = set()
    for item in _first_list(details):
        if isinstance(item, dict):
            name = _text(item.get("estateName")).strip()
            if name and name != "-":
                estate_names.add(name)
    if not estate_names:
        return {"resultList": [], "total": 0}
    # Query buildings by estate name (top 5 to avoid too many calls)
    all_buildings = []
    for name in list(estate_names)[:5]:
        result = _safe_call(T_BUILDING_QUERY, {"matchKeyword": name, "pageIndex": 1, "pageSize": page_size})
        rows = _first_list(result)
        for r in rows:
            if isinstance(r, dict):
                all_buildings.append(r)
    # Deduplicate by estateId
    seen_ids = set()
    deduped = []
    for r in all_buildings:
        eid = _text(r.get("estateId"))
        if eid and eid not in seen_ids:
            seen_ids.add(eid)
            deduped.append(r)
        elif not eid:
            deduped.append(r)
    return {"resultList": deduped, "total": len(deduped)}


def build_payload(raw: str, keyword_type: str, address: Optional[str], page_size: int, property_type: Optional[str]) -> Dict[str, Any]:
    resolved = resolve_enterprise_name(raw)
    enterprise = resolved["enterprise"]
    profile = resolved.get("profile")  # may be None for direct full-name input

    # If profile not captured during resolution (enterprise name was full), fetch it now
    if not profile:
        fuzzy = _safe_call(T_FUZZY, {"matchKeyword": enterprise, "pageSize": 1})
        profile = _extract_profile(_first_record(fuzzy))

    mk_args: Dict[str, Any] = {"matchKeyword": enterprise, "keywordType": keyword_type}

    details_args: Dict[str, Any] = {"matchKeyword": enterprise, "keywordType": keyword_type, "pageIndex": 1, "pageSize": page_size}
    if address:
        details_args["address"] = address

    details = _safe_call(T_OFFICE_DETAILS, details_args)
    stats = _safe_call(T_OFFICE_STATS, mk_args)

    # Building query: try estate-name-based lookup first, fall back to generic query
    if address or property_type:
        building_args: Dict[str, Any] = {"pageIndex": 1, "pageSize": page_size}
        if address:
            building_args["address"] = address
        if property_type:
            building_args["estatePropertyType"] = property_type
        building = _safe_call(T_BUILDING_QUERY, building_args)
    else:
        building = _query_buildings_for_estates(details, page_size)

    subject = build_subject(raw, resolved, keyword_type)
    core = build_core_analysis(details, stats, building)
    metrics = build_metrics(details, stats, building, profile)
    return _assemble(subject, core, metrics, dry_run=False, profile=profile)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="Compose a building big-data report via the building MCP.")
    parser.add_argument("--enterprise", required=True, help="企业全称或关键词（关键词将自动模糊补全）")
    parser.add_argument("--keyword-type", default="name", help="主体类型：name/nameId/regNumber/socialCreditCode")
    parser.add_argument("--address", default=None, help="可选地区筛选（省/市，英文逗号分隔，如 广东省,广州市）")
    parser.add_argument("--property-type", default=None, help="可选楼宇类型（写字楼/产业园/综合体/公寓酒店/展会中心）")
    parser.add_argument("--page-size", type=int, default=10, help="明细分页大小（最多 10）")
    parser.add_argument("--dry-run", action="store_true", help="不调用真实 MCP，使用样例数据组装报告骨架")
    parser.add_argument("--output", help="输出 JSON 路径；省略则打印到 stdout")
    parser.add_argument("--report-output", help="同时输出 HTML 报告（.html）与 Markdown 报告（.md）")
    parser.add_argument("--pdf-output", help="额外输出 PDF 报告（.pdf）；需要 Playwright + Chromium")
    args = parser.parse_args()

    if args.dry_run:
        payload = build_dry_run_payload(args.enterprise, args.keyword_type)
    else:
        payload = build_payload(args.enterprise, args.keyword_type, args.address, args.page_size, args.property_type)

    if args.output:
        out = pathlib.Path(args.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_dumps(payload, pretty=True), encoding="utf-8")
        print_json({"ok": True, "json": str(out), "dry_run": args.dry_run})
    else:
        print_json(payload)

    if args.report_output:
        base_out = pathlib.Path(args.report_output).expanduser()
        base_out.parent.mkdir(parents=True, exist_ok=True)
        html_path = base_out.with_suffix(".html") if base_out.suffix.lower() not in (".html", ".htm") else base_out
        md_path = html_path.with_suffix(".md")
        html_path.write_text(render_html(payload), encoding="utf-8")
        md_path.write_text(render_markdown(payload), encoding="utf-8")
        if args.pdf_output:
            pdf_path = pathlib.Path(args.pdf_output).expanduser()
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            html_to_pdf(render_html(payload), str(pdf_path))
        print_json({"ok": True, "html": str(html_path), "markdown": str(md_path), "pdf": str(pdf_path) if args.pdf_output else None, "dry_run": args.dry_run})


if __name__ == "__main__":
    main()
