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
import copy
import datetime as dt
import json
import pathlib
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence

from common import REPORT_BANNER, REPORT_TYPE, attach_pagination, call_tool_once, collect_detail_pages, json_dumps, load_json_file, paid_call_scope, print_json
import mcp_client
from render_report import render_html, render_markdown, html_to_pdf

SAMPLE_PATH = pathlib.Path(__file__).resolve().parent.parent / "assets" / "report.example.json"

# Building MCP tools.
T_FUZZY = "building_bigdata_fuzzy_search"
T_OFFICE_DETAILS = "building_bigdata_office_address_details"
T_OFFICE_STATS = "building_bigdata_office_address_stats"
T_BUILDING_QUERY = "building_bigdata_building_query"
T_BUILDING_BASIC = "building_bigdata_building_basic_info"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _is_api_error(value: Any) -> bool:
    """Return True for failed MCP/tool envelopes, never for a successful empty result."""
    if value is None:
        return False
    if isinstance(value, str):
        text = value.strip().lower()
        return any(marker in text for marker in (
            "接口调用失败", "查询失败", "状态码：4", "状态码：5",
            "error executing tool", "validation error", "密钥错误", "鉴权失败",
        ))
    if isinstance(value, list):
        return any(_is_api_error(item) for item in value)
    if isinstance(value, dict):
        if value.get("isError") is True or value.get("is_error") is True or value.get("success") is False:
            return True
        if value.get("_error") not in (None, "", False) or value.get("error") not in (None, "", False):
            return True
        if set(value) <= {"text", "code", "status", "message", "msg"} and value.get("text"):
            text = str(value.get("text")).strip()
            if "查询数据为空" in text:
                return False
            return True
        return any(
            _is_api_error(value.get(key))
            for key in ("text", "message", "msg", "detail", "content")
            if key in value
        )
    return False


def _first_list(value: Any) -> List[Any]:
    """Extract business records without turning envelopes into phantom rows."""
    if _is_api_error(value):
        return []
    if isinstance(value, list):
        cleaned: List[Any] = []
        for item in value:
            if _is_api_error(item) or item in (None, "", {}, []):
                continue
            if isinstance(item, dict):
                business_values = [v for k, v in item.items() if k not in {"total", "count", "code", "message", "msg"}]
                if business_values and all(v in (None, "", "-", [], {}) for v in business_values):
                    continue
            cleaned.append(item)
        return cleaned
    if isinstance(value, dict):
        for key in ("resultList", "storeList", "list", "items", "data", "records"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
        envelope_keys = {
            "text", "message", "msg", "code", "status", "success", "total", "count",
            "pageIndex", "pageSize", "isError", "is_error", "content", "structuredContent",
            "structured_content", "_error", "error",
        }
        if set(value) <= envelope_keys:
            return []
        if value:
            return [value]
    return []


def _first_record(value: Any) -> Dict[str, Any]:
    for record in _first_list(value):
        if isinstance(record, dict) and not _is_api_error(record):
            return record
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
        result = call_tool_once(mcp_client.call_tool, tool, arguments)
        # Detect API error responses (405, etc.) and return error marker
        if _is_api_error(result):
            return {"_error": "API错误", "_raw": result}
        return result
    except Exception:
        return {"_error": "调用失败"}


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


def _failed_tools(sources: Mapping[str, Any]) -> List[str]:
    """Return only safe tool/dimension labels for failed calls."""
    return [name for name, payload in sources.items() if _is_api_error(payload)]


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
    fuzzy_total = _int(_safe_total(fuzzy))
    if fuzzy_total is not None and fuzzy_total > 1:
        return {
            "keyword": raw,
            "enterprise": raw,
            "resolved": False,
            "reason": f"模糊查询返回多候选（{fuzzy_total}），未静默选择首条",
            "fuzzy_total": fuzzy_total,
        }
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
    products = [item["name"] for item in _requested_product_rows(subject)]
    return {
        "match_target": subject.get("enterprise") or subject.get("match_raw"),
        "match_type": f"楼宇/办公地址数据按企业主体匹配（keywordType={subject.get('keywordType', 'name')}）；楼宇查询支持按地区/楼宇类型/关键词检索",
        "data_scope": "、".join(products),
        "products": products,
        "limit": "地址与入驻信息仅为公开数据线索，可能存在更新延迟；不证明楼宇/房产所有权、持续租赁、实际办公或人员驻场。地区筛选明细不得与全国统计交叉计算比率。",
    }


def _requested_product_rows(subject: Mapping[str, Any]) -> List[Dict[str, str]]:
    """List resolver and analysis products actually requested for this scope."""
    rows = [{"name": "企业模糊查询", "product_id": "675cea1f0e009a9ea37edaa1"}]
    if subject.get("blocked_reason"):
        return rows
    rows.extend([
        {"name": "企业办公地址详情", "product_id": "6786528b1677add9f934358f"},
        {"name": "企业办公地址统计", "product_id": "6786528b1677add9f934359d"},
    ])
    if subject.get("building_query_scope") == "explicit_estate_id_association":
        rows.append({"name": "楼宇基础信息", "product_id": "6786528b1677add9f93435b4"})
    else:
        rows.append({"name": "楼宇查询", "product_id": "6786528b1677add9f93435db"})
    return rows


def build_metrics(details: Any, stats: Any, building: Any, profile: Optional[Mapping[str, Any]] = None, *, filtered: bool = False, market_building_query: bool = False) -> List[Dict[str, Any]]:
    metrics: List[Dict[str, Any]] = []
    d_total = _int(_safe_total(details)) if isinstance(details, dict) else None
    s = stats if isinstance(stats, dict) else {}
    city_list = s.get("officeCityStats") if isinstance(s.get("officeCityStats"), list) else []
    city_count = len(city_list) if isinstance(city_list, list) else None
    b_total = _int(_safe_total(building)) if isinstance(building, dict) else None

    # --- Office address metrics ---
    detail_label = "筛选地区办公地址数" if filtered else "办公地址总数"
    detail_hint = ("本次地区筛选命中的办公地址数，不是企业全国总数" if filtered else "企业办公地址总数")
    metrics.append({"label": detail_label, "value": (_text(d_total) if d_total is not None else "-"), "hint": detail_hint})
    if not filtered and city_count and d_total:
        metrics.append({"label": "覆盖城市数", "value": _text(city_count), "hint": "办公地址所涉城市数", "delta": f"地均 {d_total / city_count:.1f} 个/城"})
    elif not filtered and city_count:
        metrics.append({"label": "覆盖城市数", "value": _text(city_count), "hint": "办公地址所涉城市数"})

    # Province count (derived from the detail page; scope follows that page)
    province_rows = _office_province_rows(details)
    if province_rows:
        metrics.append({
            "label": "筛选地区覆盖省份数" if filtered else "覆盖省份数",
            "value": str(len(province_rows)),
            "hint": "仅按筛选后明细去重，不代表企业全国省份覆盖" if filtered else "办公地址所涉省份数",
        })

    # CR3 city concentration (national stats are valid even when details are filtered)
    stat_rows = _office_stat_rows(stats)
    if stat_rows:
        conc = _concentration(stat_rows, "城市", "办公地址数量", 3)
        if conc:
            metrics.append({
                "label": "全国统计CR3" if filtered else "CR3城市集中度",
                "value": f"{conc['cr']:.0f}%",
                "hint": (f"全国城市统计前3合计，TOP1：{conc['top']}；与筛选明细不可交叉计算"
                         if filtered else f"前3城市合计，TOP1：{conc['top']}"),
                "scope": "national_stats",
            })

    # --- Building metrics ---
    if b_total is not None and b_total > 0:
        metrics.append({"label": "筛选楼宇命中量" if market_building_query else "明确ID关联楼宇数", "value": _text(b_total), "hint": "独立楼宇筛选结果，不代表企业关联" if market_building_query else "仅统计办公地址明细明确返回楼宇ID的记录", "scope": "market" if market_building_query else "enterprise"})

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
            "楼宇ID": _text(item.get("estateId")) or "-",
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
            "楼宇ID": _text(item.get("estateId")) or "-",
            "关联依据": _text(item.get("associationEvidence")) or "-",
        })
    return out


def _building_type_rows(building_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
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


def _concentration(rows: Sequence[Mapping[str, Any]], name_key: str, value_key: str, top_n: int = 3) -> Dict[str, Any]:
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


def build_core_analysis(details: Any, stats: Any, building: Any, *, filtered: bool = False, market_building_query: bool = False) -> Dict[str, Any]:
    detail_rows = _office_detail_rows(details)
    stat_rows = _office_stat_rows(stats)
    building_rows = _building_rows(building)
    building_type_rows = _building_type_rows(building_rows)
    office_province_rows = _office_province_rows(details)
    settle_type_rows = _office_settle_type_rows(details)
    source_type_rows = _office_source_type_rows(details)

    sections = [
        {"key": "office_details", "title": "办公地址详情", "kind": "table",
         "note": f"展示 {len(detail_rows)} 条办公地址记录" + (f"；上游总量 {_safe_total(details)}" if _safe_total(details) is not None else "；上游未返回总量"),
         "columns": [("办公地址", "办公地址"), ("所在城市", "所在城市"), ("所在区域", "所在区域"), ("所在楼宇", "所在楼宇"), ("楼宇ID", "楼宇ID"), ("入驻方式", "入驻方式"), ("地址来源", "地址来源")]},
        {"key": "office_province", "title": "办公地址省份分布", "kind": "bar",
         "note": "按办公地址所在省份聚合办公点数量",
         "chart": {"name": "省份", "value": "办公点数", "orient": "h"},
         "columns": [("省份", "省份"), ("办公点数", "办公点数")]},
        {"key": "office_stats", "title": "办公地址城市分布（全国口径）", "kind": "donut", "note": "企业全国办公地址统计；不与地区筛选后的明细交叉计算比率" if filtered else "按企业全国办公地址统计城市分布",
         "chart": {"name": "城市", "value": "办公地址数量"},
         "columns": [("城市", "城市"), ("办公地址数量", "办公地址数量")]},
        {"key": "settle_type", "title": "入驻方式分布", "kind": "donut", "note": "按入驻方式（工商注册入驻 / 办公地址入驻）统计",
         "chart": {"name": "入驻方式", "value": "数量"},
         "columns": [("入驻方式", "入驻方式"), ("数量", "数量")]},
        {"key": "source_type", "title": "地址来源分布", "kind": "donut", "note": "按地址来源类型（工商登记 / 办公地址 / 招聘信息）统计",
         "chart": {"name": "地址来源", "value": "数量"},
         "columns": [("地址来源", "地址来源"), ("数量", "数量")]},
        {"key": "building_query", "title": "独立楼宇筛选明细" if market_building_query else "明确ID关联楼宇明细", "kind": "table",
         "note": ("独立地区/类型筛选，不代表与查询企业关联；" if market_building_query else "仅由办公地址明细明确返回的楼宇ID关联；") + f"展示 {len(building_rows)} 个楼盘" + (f"；上游总量 {_safe_total(building)}" if _safe_total(building) is not None else "；上游未返回总量"),
         "columns": [("楼宇名称", "楼宇名称"), ("楼宇ID", "楼宇ID"), ("楼宇类型", "楼宇类型"), ("楼宇地址", "楼宇地址"), ("入驻企业数", "入驻企业数"), ("关联依据", "关联依据")]},
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
        "building_query_scope": "market_filter" if market_building_query else "enterprise_association",
        "scope_note": "地区筛选仅作用于办公地址明细与楼宇查询；办公地址城市统计为全国口径。" if filtered else "办公地址明细与统计均按企业主体查询。",
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


def build_insights(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: Sequence[Mapping[str, Any]], profile: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
    insights: List[Dict[str, Any]] = []
    metric_map = {m["label"]: str(m["value"]) for m in metrics}
    addr_total = metric_map.get("办公地址总数") or metric_map.get("筛选地区办公地址数")
    addr_is_filtered = "办公地址总数" not in metric_map
    city_count = metric_map.get("覆盖城市数")
    building_total = metric_map.get("筛选楼宇命中量") or metric_map.get("明确ID关联楼宇数") or metric_map.get("楼宇库存量")

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
            "feature": "筛选地区办公地址规模" if addr_is_filtered else "办公地址规模",
            "evidence": (f"本次地区筛选命中办公地址 {addr_total}{extra}；不是企业全国办公地址总数。"
                         if addr_is_filtered else f"企业办公地址总数 {addr_total}{extra}。"),
            "interpretation": "办公地址记录仅是公开来源线索，可用于后续核验；不能据此推断资产所有权、持续入驻、人员规模或实际经营状态。",
        })

    # 2. City concentration
    stat_rows = core.get("office_stats") or []
    if stat_rows:
        conc = _concentration(stat_rows, "城市", "办公地址数量", 3)
        if conc:
            nationwide = "地区筛选下仍为全国统计口径；" if "地区筛选" in str(core.get("scope_note")) else ""
            insights.append({
                "feature": "全国口径城市分布集中度",
                "evidence": f"{nationwide}“{conc['top']}”公开办公地址统计占比约 {conc['top_share']:.0f}%，全国前 3 城市合计 {conc['cr']:.0f}%（CR3）。",
                "interpretation": "该集中度只描述公开地址统计的全国分布，不与地区筛选明细合并，也不证明实际经营覆盖或地址所有权。",
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

    # 4. Settle type structure (detail page scope)
    settle_rows = core.get("settle_type") or []
    if settle_rows:
        total_settle = sum(int(r.get("数量", 0)) for r in settle_rows)
        if total_settle:
            top_settle = settle_rows[0].get("入驻方式", "")
            top_count = int(settle_rows[0].get("数量", 0))
            top_pct = top_count / total_settle * 100
            scope = "本次展示的筛选地区明细" if addr_is_filtered else "本次展示的办公地址明细"
            insights.append({
                "feature": "入驻方式结构",
                "evidence": f"{scope}中，“{top_settle}”占比约 {top_pct:.0f}%（{top_count}/{total_settle}）。",
                "interpretation": "入驻方式是公开数据源的分类标签，仅用于线索分组；不能单独证明当前实际占用或持续经营。",
            })

    # 5. Source type structure (detail page scope)
    source_rows = core.get("source_type") or []
    if source_rows and len(source_rows) > 1:
        total_source = sum(int(r.get("数量", 0)) for r in source_rows)
        if total_source:
            top_source = source_rows[0].get("地址来源", "")
            top_count = int(source_rows[0].get("数量", 0))
            top_pct = top_count / total_source * 100
            scope = "本次展示的筛选地区明细" if addr_is_filtered else "本次展示的办公地址明细"
            insights.append({
                "feature": "地址来源多样性",
                "evidence": f"{scope}中，地址来源覆盖 {len(source_rows)} 种渠道，“{top_source}”占比约 {top_pct:.0f}%。",
                "interpretation": "多来源地址意味着企业在工商登记、办公点、招聘等渠道均有露出；该比例只描述展示样本，不代表全量来源结构。",
            })

    # 6. Building enterprise density (market filter total vs displayed sample)
    building_rows = core.get("building_query") or []
    if building_rows:
        try:
            ent_vals = [float(str(r.get("入驻企业数", "0")).replace(",", "")) for r in building_rows if r.get("入驻企业数") and str(r.get("入驻企业数")).replace(",", "").replace(".", "").isdigit()]
            if ent_vals:
                avg_ent = sum(ent_vals) / len(ent_vals)
                is_associated = any(row.get("关联依据") not in (None, "", "-") for row in building_rows)
                if is_associated:
                    evidence = f"办公地址明细明确关联 {len(building_rows)} 个楼盘，单楼入驻企业均值约 {avg_ent:.0f} 家。"
                else:
                    hit_text = f"筛选命中 {building_total} 个楼盘，" if building_total else ""
                    evidence = f"{hit_text}本次展示 {len(building_rows)} 个；展示样本单楼入驻企业均值约 {avg_ent:.0f} 家。"
                insights.append({
                    "feature": "关联楼宇公开入驻量" if is_associated else "楼宇承载密度",
                    "evidence": evidence,
                    "interpretation": ("这些楼宇均由办公地址明细中的明确楼宇ID关联；入驻企业数仅为楼宇公开统计，不证明查询企业拥有该楼宇。"
                                       if is_associated else "楼宇入驻密度仅描述当前展示的筛选结果，可作为区域供给线索，不能外推全部命中楼盘或未返回楼宇。"),
                })
        except (TypeError, ValueError):
            pass

    # 7. Building type structure (skip when the filter itself fixes the type)
    type_rows = core.get("building_type") or []
    if type_rows and not (core.get("building_query_scope") == "market_filter" and len(type_rows) == 1):
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


def build_abstract(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: Sequence[Mapping[str, Any]], profile: Optional[Mapping[str, Any]] = None) -> str:
    name = subject.get("enterprise") or subject.get("match_raw") or "目标企业"
    has_office = bool(core.get("office_details") or core.get("office_stats"))
    has_building = bool(core.get("building_query"))
    parts = [f"本报告以“{name}”为分析对象，基于楼宇/办公地址大数据。"]
    if has_office:
        parts.append("报告呈现企业办公地址详情与地址分布统计。")
        if has_building:
            parts.append("另附楼宇查询明细。")
    else:
        parts.append("本次未获得该企业办公地址明细；报告仅呈现独立楼宇筛选结果，不据此推断企业办公布局。")
    enterprise_metrics = [m for m in metrics if str(m.get("scope") or "") != "market"]
    if enterprise_metrics:
        kv = "、".join(f"{m['label']} {m['value']}" for m in enterprise_metrics[:5])
        parts.append(f"关键指标包括：{kv}。")
    parts.append("楼宇查询结果不代表与查询企业关联；选址与招商判断需逐条核验。")
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
    return apply_content_review(_assemble(subject, core, metrics, dry_run=True))


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def _quality_report(core: Mapping[str, Any]) -> Dict[str, Any]:
    """Section-fill rate from final declared sections and their actual bodies.

    ``0`` is a populated body; None/''/[]/{} is empty. Not an accuracy score.
    """
    ca = core if isinstance(core, dict) else {}
    sections = ca.get("sections")
    if isinstance(sections, list):
        total = len(sections)
        populated = sum(1 for s in sections if isinstance(s, dict) and ca.get(s.get("key")) not in (None, "", [], {}))
    else:
        keys = [k for k in ca if k not in ("sections", "source_status")]
        total = len(keys)
        populated = sum(1 for k in keys if ca.get(k) not in (None, "", [], {}))
    return {
        "total_sections": total,
        "populated_sections": populated,
        "empty_sections": total - populated,
        "coverage_pct": round(populated / max(1, total) * 100),
    }


def _assemble(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: Sequence[Mapping[str, Any]], *, dry_run: bool, profile: Optional[Mapping[str, Any]] = None, tool_errors: Optional[List[str]] = None) -> Dict[str, Any]:
    abstract = build_abstract(subject, core, metrics, profile)
    records = build_records(core)
    insights = build_insights(subject, core, metrics, profile)
    quality_report = _quality_report(core)
    populated = quality_report["populated_sections"]
    if populated == 0:
        if subject.get("blocked_reason"):
            abstract = f"主体未唯一解析，已停止后续数据产品调用：{subject.get('blocked_reason')}。本报告不包含主体画像或业务结论。"
        elif tool_errors:
            abstract = "本次查询未获得有效核心数据，且存在上游调用失败维度：" + "、".join(tool_errors) + "。不据此生成业务规模或市场结论。"
        else:
            abstract = "本次查询未返回有效核心数据；报告仅记录查询边界，不生成业务规模或市场结论。"
        print("⚠️ 质量门禁警告: 所有核心分析维度均无数据", file=sys.stderr)
    title = f"{subject.get('enterprise') or '目标企业'} 楼宇大数据报告"
    return {
        "report_type": REPORT_TYPE,
        "title": title,
        "banner": REPORT_BANNER,
        "subject": dict(subject),
        "abstract": abstract,
        "summary": abstract,
        "executive_summary": ((["主体解析受阻：" + str(subject.get("blocked_reason")) + "；已停止主体数据调用。"] if subject.get("blocked_reason") else (["数据缺口：" + "、".join(tool_errors or []) + "未成功返回，本报告仅呈现成功维度。"] if tool_errors else [])) + ([item["interpretation"] for item in insights][:5] or [abstract[:120]])),
        "metrics": list(metrics),
        "caliber": build_caliber(subject),
        "core_analysis": dict(core),
        "representative_records": records,
        "insights": insights,
        "data_source": {
            "mcp_server": "building-mcp-server",
            "products": _requested_product_rows(subject),
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "dry_run": dry_run,
            "tool_errors": list(tool_errors or []),
            "blocked_reason": subject.get("blocked_reason"),
            "quality_report": quality_report,
        },
    }


def _query_buildings_for_estates(details: Any, page_size: int = 10) -> Any:
    """Fetch building basics only from explicit estate IDs in office details."""
    del page_size  # basic-info is not paginated
    estate_ids = {
        _text(item.get("estateId")).strip()
        for item in _first_list(details)
        if isinstance(item, dict) and _text(item.get("estateId")).strip()
    }
    all_buildings: List[Dict[str, Any]] = []
    for estate_id in sorted(estate_ids):
        result = _safe_call(T_BUILDING_BASIC, {"matchKeyword": estate_id})
        record = _first_record(result)
        if not record:
            continue
        row = dict(record)
        row.setdefault("estateId", estate_id)
        row["associationEvidence"] = "办公地址明细明确返回的楼宇ID"
        all_buildings.append(row)
    return {"resultList": all_buildings, "total": len(all_buildings)}


def _review_metrics(metrics: Sequence[Mapping[str, Any]], filtered: bool) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for raw in metrics:
        if not isinstance(raw, dict):
            continue
        metric = dict(raw)
        label = str(metric.get("label") or "")
        if filtered and label == "办公地址总数":
            label = "筛选地区办公地址数"
            metric["hint"] = "本次地区筛选命中的办公地址数，不是企业全国总数"
        elif filtered and label == "覆盖省份数":
            label = "筛选地区覆盖省份数"
            metric["hint"] = "仅按筛选后明细去重，不代表企业全国省份覆盖"
        elif filtered and label == "CR3城市集中度":
            label = "全国统计CR3"
            metric["hint"] = "全国城市统计前3合计；与筛选明细不可交叉计算"
            metric["scope"] = "national_stats"
        if label == "筛选楼宇命中量":
            metric["scope"] = "market"
        metric["label"] = label
        if label in seen:
            continue
        seen.add(label)
        out.append(metric)
    return out


def apply_content_review(report: Mapping[str, Any], *, source_sha256: Optional[str] = None,
                         reviewed_at: Optional[str] = None) -> Dict[str, Any]:
    """Rebuild building narrative content offline from an existing payload.

    Uses only fields already present (office details/stats, building rows,
    metrics, subject, generated_at). No MCP call, no new facts. Fixes filtered
    detail counts being labelled as enterprise totals, sample-only entry/source
    shares presented as full-population shares, market-filter hit counts written
    as "命中 N 个楼盘", and a tautological building-type share when the query
    itself filtered one type. Only an actual address filter changes the office
    count to the filtered scope; a property-type-only market query does not.
    """
    out = copy.deepcopy(dict(report))
    core = dict(out.get("core_analysis") or {})
    subject = dict(out.get("subject") or {})
    ds = dict(out.get("data_source") or {})
    if subject.get("blocked_reason") or ds.get("blocked_reason"):
        ds["quality_report"] = _quality_report(core)
        ds["content_revision"] = {
            "mode": "offline_source_preserving",
            "source_sha256": source_sha256,
            "original_generated_at": ds.get("generated_at"),
            "reviewed_at": reviewed_at or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "scope": "主体未唯一解析/受阻报告：保留原阻断说明与空结果边界，不重算业务结论",
        }
        out["data_source"] = ds
        return out
    scope_note = str(core.get("scope_note") or "")
    address_filtered = subject.get("address_filtered")
    if address_filtered is None:
        # Reports generated before the explicit flag carried the address scope
        # only in scope_note; fall back to that same evidence.
        address_filtered = "地区筛选" in scope_note
    filtered = bool(address_filtered)
    if subject.get("building_query_scope") == "independent_market_filter":
        core["building_query_scope"] = "market_filter"
    metrics = _review_metrics(out.get("metrics") or [], filtered)
    quality = _quality_report(core)
    if quality["populated_sections"] == 0:
        # No business body: keep the assembled empty/failure narrative instead
        # of replacing it with a generic abstract that implies sections exist.
        out["core_analysis"] = core
        out["metrics"] = metrics
        ds["quality_report"] = quality
        ds["content_revision"] = {
            "mode": "offline_source_preserving",
            "source_sha256": source_sha256,
            "original_generated_at": ds.get("generated_at"),
            "reviewed_at": reviewed_at or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "scope": "无有效业务章节：保留原始空结果或调用失败说明，不生成业务结论",
        }
        out["data_source"] = ds
        return out
    old_profile_insights = [i for i in (out.get("insights") or []) if isinstance(i, dict) and i.get("feature") == "企业背景概况"]
    insights = build_insights(subject, core, metrics, profile=None)
    if old_profile_insights and not any(i.get("feature") == "企业背景概况" for i in insights):
        insights.extend(old_profile_insights)
    abstract = build_abstract(subject, core, metrics, profile=None)
    old_abstract = str(out.get("abstract") or "")
    marker = "明细含未完整采集的来源"
    if marker in old_abstract:
        # attach_pagination() appends this disclosure after the review; keep it
        # when an already-attached report is reviewed again offline.
        abstract += old_abstract[old_abstract.index(marker):]
    out["core_analysis"] = core
    out["metrics"] = metrics
    out["insights"] = insights
    out["abstract"] = abstract
    out["summary"] = abstract
    gap_lines = []
    if ds.get("tool_errors"):
        gap_lines = ["数据缺口：" + "、".join(str(item) for item in ds["tool_errors"]) + "未成功返回，本报告仅呈现成功维度。"]
    insight_lines = [i.get("interpretation") for i in insights][:5] or [abstract[:120]]
    out["executive_summary"] = gap_lines + insight_lines
    ds["quality_report"] = quality
    ds["content_revision"] = {
        "mode": "offline_source_preserving",
        "source_sha256": source_sha256,
        "original_generated_at": ds.get("generated_at"),
        "reviewed_at": reviewed_at or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "区分筛选明细与全国统计口径；重算样本占比文案；未新增查询、未改写原始记录",
    }
    out["data_source"] = ds
    return out


@paid_call_scope
def build_payload(raw: str, keyword_type: str, address: Optional[str], page_size: int, property_type: Optional[str], max_pages: int = 1) -> Dict[str, Any]:
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError("max_pages 必须为正整数")
    resolved = resolve_enterprise_name(raw)
    enterprise = resolved["enterprise"]
    if not resolved.get("resolved"):
        subject = build_subject(raw, resolved, keyword_type)
        subject["blocked_reason"] = resolved.get("reason") or "企业主体未唯一解析"
        report = _assemble(subject, build_core_analysis({}, {}, {}), [], dry_run=False, profile=None)
        report["data_source"]["blocked_reason"] = subject["blocked_reason"]
        return apply_content_review(report)
    profile = resolved.get("profile")  # may be None for direct full-name input

    # If profile not captured during resolution (enterprise name was full), fetch it now
    if not profile:
        fuzzy = _safe_call(T_FUZZY, {"matchKeyword": enterprise, "pageSize": 1})
        profile = _extract_profile(_first_record(fuzzy))

    mk_args: Dict[str, Any] = {"matchKeyword": enterprise, "keywordType": keyword_type}

    details_args: Dict[str, Any] = {"matchKeyword": enterprise, "keywordType": keyword_type, "pageSize": page_size}
    if address:
        details_args["address"] = address

    details = collect_detail_pages(_safe_call, T_OFFICE_DETAILS, details_args,
                                   get_rows=_first_list, get_total=_safe_total, is_error=_is_api_error,
                                   max_pages=max_pages)
    stats = _safe_call(T_OFFICE_STATS, mk_args)

    # Building query: try estate-name-based lookup first, fall back to generic query
    if address or property_type:
        building_args: Dict[str, Any] = {"pageSize": page_size}
        if address:
            building_args["address"] = address
        if property_type:
            building_args["estatePropertyType"] = property_type
        building = collect_detail_pages(_safe_call, T_BUILDING_QUERY, building_args,
                                        get_rows=_first_list, get_total=_safe_total, is_error=_is_api_error,
                                        max_pages=max_pages)
    else:
        building = _query_buildings_for_estates(details, page_size)

    subject = build_subject(raw, resolved, keyword_type)
    market_building_query = bool(address or property_type)
    subject["building_query_scope"] = "independent_market_filter" if market_building_query else "explicit_estate_id_association"
    # Address filtering scopes the office-address counts; a property-type-only
    # market search leaves the enterprise office totals unfiltered.
    subject["address_filtered"] = bool(address)
    core = build_core_analysis(details, stats, building, filtered=bool(address), market_building_query=market_building_query)
    metrics = build_metrics(details, stats, building, profile, filtered=bool(address), market_building_query=market_building_query)
    report = apply_content_review(_assemble(subject, core, metrics, dry_run=False, profile=profile, tool_errors=_failed_tools({"企业办公地址详情": details, "企业办公地址统计": stats, "楼宇查询": building})))
    return attach_pagination(report, {"办公地址明细": details, "楼宇查询": building})


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
    parser.add_argument("--max-pages", type=int, default=1, help="规划的明细付费调用页数上限，默认1；先按 total 估算，只有必要且已授权时提高")
    parser.add_argument("--dry-run", action="store_true", help="不调用真实 MCP，使用样例数据组装报告骨架")
    parser.add_argument("--output", help="输出 JSON 路径；省略则打印到 stdout")
    parser.add_argument("--report-output", help="同时输出 HTML 报告（.html）与 Markdown 报告（.md）")
    parser.add_argument("--pdf-output", help="额外输出 PDF 报告（.pdf）；需要 Playwright + Chromium")
    args = parser.parse_args()

    if args.max_pages is not None and args.max_pages < 1:
        raise SystemExit("--max-pages 必须为正整数")

    if args.dry_run:
        payload = build_dry_run_payload(args.enterprise, args.keyword_type)
    else:
        payload = build_payload(args.enterprise, args.keyword_type, args.address, args.page_size, args.property_type, args.max_pages)

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
