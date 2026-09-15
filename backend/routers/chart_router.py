from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
import models
from auth import get_current_user

router = APIRouter(prefix="/charts", tags=["指标趋势图表数据"])

ALIAS_GROUPS = [
    ["CA199", "CA19-9", "CA-199", "糖类抗原199", "糖类抗原19-9"],
    ["CA125", "CA-125", "糖类抗原125"],
    ["CA153", "CA-153", "CA15-3", "糖类抗原153"],
    ["CYFRA21-1", "CYFRA211", "CYFRA 21-1"],
    ["AFP", "甲胎蛋白"],
    ["NSE"],
    ["CEA", "癌胚抗原"],
    ["WBC", "白细胞", "白细胞计数"],
    ["PLT", "血小板", "血小板计数"],
    ["NEUT#", "NEUT", "中性粒细胞绝对值", "中性粒细胞"],
    ["HGB", "HB", "血红蛋白"],
    ["ALT", "GPT", "谷丙转氨酶"],
    ["AST", "GOT", "谷草转氨酶"],
    ["CR", "CREA", "CRE", "血肌酐", "肌酐"],
    ["GLU", "GLUCOSE", "血糖", "空腹血糖"],
    ["UA", "URIC", "尿酸"],
    ["TBIL", "总胆红素"],
    ["ALB", "白蛋白"]
]

ALIAS_MAP = {}
CANONICAL_MAP = {}
for group in ALIAS_GROUPS:
    canonical = group[0].upper()
    for alias in group:
        upper_alias = alias.upper()
        ALIAS_MAP[upper_alias] = [a.upper() for a in group]
        CANONICAL_MAP[upper_alias] = canonical

from services.unit_converter import normalize_lab_unit_and_value, STANDARD_UNITS

def determine_item_status(val: Any, ref_min: Any, ref_max: Any, raw_status: Any) -> str:
    """综合测定数值与参考区间判定指标是否异常 (HIGH / LOW / ABNORMAL / NORMAL)"""
    if val is not None and ref_max is not None:
        try:
            if float(val) > float(ref_max):
                return "HIGH"
        except (ValueError, TypeError):
            pass
    if val is not None and ref_min is not None:
        try:
            if float(val) < float(ref_min):
                return "LOW"
        except (ValueError, TypeError):
            pass
    raw = (raw_status or "").strip().upper()
    if raw in ("HIGH", "LOW", "ABNORMAL"):
        return raw
    return "NORMAL"

@router.get("/overview")
def get_chart_overview(
    target_user_id: int = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    指标看板全景概览数据：
    1. 最近一次采样检验的综合态势快照（采样日期、总项数、正常项数、关注项数、关注清单）
    2. 核心 KPI 聚焦卡片（优先提取当前异常指标 + 核心肿瘤/血液/代谢指标，含微缩 Sparkline 时序走势）
    3. 各类目指标数量分布统计
    """
    user_id = target_user_id if (current_user.is_admin and target_user_id) else current_user.id

    items = db.query(models.LabItem).filter(
        models.LabItem.user_id == user_id,
        models.LabItem.item_code != None,
        models.LabItem.item_code != "",
        models.LabItem.test_date != None,
        models.LabItem.test_date != ""
    ).order_by(models.LabItem.test_date.asc(), models.LabItem.id.asc()).all()

    if not items:
        return {
            "has_data": False,
            "latest_date": None,
            "latest_stats": {
                "total_items": 0,
                "normal_count": 0,
                "abnormal_count": 0,
                "abnormal_items": []
            },
            "kpi_cards": [],
            "categories": {
                "tumor_marker": 0,
                "safety_toxicity": 0,
                "chronic": 0,
                "other": 0
            }
        }

    # 1. 获取所有不重复的采样日期
    dates = sorted(list({it.test_date for it in items if it.test_date}))
    latest_date = dates[-1]

    # 2. 按标准缩写聚合所有指标历史
    grouped = {}
    for it in items:
        raw_code = (it.item_code or "").strip()
        code_upper = raw_code.upper()
        canon = CANONICAL_MAP.get(code_upper, code_upper)

        norm_res = normalize_lab_unit_and_value(
            item_code=canon,
            value=it.value,
            unit=it.unit,
            ref_min=it.ref_min,
            ref_max=it.ref_max,
            ref_range=it.ref_range
        )
        st = determine_item_status(norm_res["value"], norm_res["ref_min"], norm_res["ref_max"], it.status)

        if canon not in grouped:
            grouped[canon] = {
                "code": canon,
                "raw_code": raw_code,
                "name": it.item_name or canon,
                "category": it.category or "other",
                "unit": norm_res["unit"] or STANDARD_UNITS.get(canon, it.unit or ""),
                "ref_min": norm_res["ref_min"],
                "ref_max": norm_res["ref_max"],
                "ref_range": norm_res["ref_range"] or it.ref_range or "",
                "records": []
            }
        
        if norm_res["ref_max"] is not None:
            grouped[canon]["ref_min"] = norm_res["ref_min"]
            grouped[canon]["ref_max"] = norm_res["ref_max"]
            grouped[canon]["ref_range"] = norm_res["ref_range"] or it.ref_range or ""

        # 单日内去重，保留当日最新一条
        rec_data = {
            "date": it.test_date,
            "value": norm_res["value"],
            "raw_value": norm_res["raw_value"],
            "raw_unit": norm_res["raw_unit"],
            "is_converted": norm_res["is_converted"],
            "status": st
        }
        existing_idx = next((i for i, r in enumerate(grouped[canon]["records"]) if r["date"] == it.test_date), None)
        if existing_idx is not None:
            grouped[canon]["records"][existing_idx] = rec_data
        else:
            grouped[canon]["records"].append(rec_data)

    # 3. 统计最新一次采样的指标状况
    latest_items_info = []
    for canon, g in grouped.items():
        on_latest = [r for r in g["records"] if r["date"] == latest_date]
        if on_latest:
            latest_items_info.append({
                "canon": canon,
                "name": g["name"],
                "record": on_latest[-1]
            })

    total_items_on_latest = len(latest_items_info)
    abnormal_items_on_latest = [
        item["name"] or item["canon"]
        for item in latest_items_info
        if item["record"]["status"] != "NORMAL"
    ]
    abnormal_count_on_latest = len(abnormal_items_on_latest)
    normal_count_on_latest = max(0, total_items_on_latest - abnormal_count_on_latest)

    # 4. 统计各类目指标数量
    categories_cnt = {
        "tumor_marker": sum(1 for g in grouped.values() if g["category"] == "tumor_marker"),
        "safety_toxicity": sum(1 for g in grouped.values() if g["category"] == "safety_toxicity"),
        "chronic": sum(1 for g in grouped.values() if g["category"] == "chronic"),
        "other": sum(1 for g in grouped.values() if g["category"] == "other")
    }

    # 5. 提炼核心 KPI 关注卡片 (最多 4 张)
    candidates = []
    for canon, g in grouped.items():
        recs = g["records"]
        if not recs:
            continue
        latest_rec = recs[-1]
        prev_rec = recs[-2] if len(recs) >= 2 else None

        delta = None
        trend = "—"
        if prev_rec and latest_rec["value"] is not None and prev_rec["value"] is not None:
            delta = round(latest_rec["value"] - prev_rec["value"], 2)
            if delta > 0:
                trend = "↑"
            elif delta < 0:
                trend = "↓"
            else:
                trend = "—"

        status = latest_rec["status"]
        status_label = "正常"
        if status == "HIGH":
            status_label = "偏高"
        elif status == "LOW":
            status_label = "偏低"
        elif status == "ABNORMAL":
            status_label = "异常"

        # 微缩 Sparkline（最近 8 次测试记录）
        sparkline = [
            {"date": r["date"], "value": r["value"]}
            for r in recs[-8:]
            if r["value"] is not None
        ]

        candidates.append({
            "code": canon,
            "name": g["name"],
            "category": g["category"],
            "unit": g["unit"],
            "latest_value": latest_rec["value"],
            "raw_value": latest_rec["raw_value"],
            "raw_unit": latest_rec["raw_unit"],
            "is_converted": latest_rec["is_converted"],
            "status": status,
            "status_label": status_label,
            "prev_value": prev_rec["value"] if prev_rec else None,
            "delta": delta,
            "trend": trend,
            "ref_min": g["ref_min"],
            "ref_max": g["ref_max"],
            "ref_range": g["ref_range"],
            "sparkline": sparkline,
            "points_count": len(recs)
        })

    # 排序评分：
    # 异常排最前 (0 vs 1)
    # 分类权重：肿瘤 > 安全性 > 慢病 > 其他
    # 核心经典指标优先
    CORE_METRICS_ORDER = ["CEA", "CA199", "CA125", "WBC", "PLT", "NEUT#", "ALT", "CR", "GLU", "HbA1c"]

    def candidate_score(c):
        is_abn = 0 if c["status"] in ("HIGH", "LOW", "ABNORMAL") else 1
        cat_order = {"tumor_marker": 0, "safety_toxicity": 1, "chronic": 2, "other": 3}.get(c["category"], 4)
        core_idx = CORE_METRICS_ORDER.index(c["code"]) if c["code"] in CORE_METRICS_ORDER else 99
        return (is_abn, cat_order, core_idx, -c["points_count"])

    candidates.sort(key=candidate_score)
    kpi_cards = candidates[:4]

    return {
        "has_data": True,
        "latest_date": latest_date,
        "latest_stats": {
            "total_items": total_items_on_latest,
            "normal_count": normal_count_on_latest,
            "abnormal_count": abnormal_count_on_latest,
            "abnormal_items": abnormal_items_on_latest
        },
        "kpi_cards": kpi_cards,
        "categories": categories_cnt
    }

@router.get("/available-metrics")
def get_available_metrics(
    target_user_id: int = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取指定用户所有已记录的指标清单（智能去重、基准单位对齐，并附带最新测定数值与健康状态）"""
    user_id = target_user_id if (current_user.is_admin and target_user_id) else current_user.id
    items = db.query(models.LabItem).filter(
        models.LabItem.user_id == user_id,
        models.LabItem.item_code != None,
        models.LabItem.item_code != ""
    ).order_by(models.LabItem.test_date.desc(), models.LabItem.id.desc()).all()

    result = []
    seen = set()
    for it in items:
        raw_code = (it.item_code or "").strip()
        code_upper = raw_code.upper()
        canon = CANONICAL_MAP.get(code_upper, code_upper)
        if canon in seen:
            continue
        seen.add(canon)
        std_unit = STANDARD_UNITS.get(canon, it.unit or "")
        norm_res = normalize_lab_unit_and_value(
            item_code=canon,
            value=it.value,
            unit=it.unit,
            ref_min=it.ref_min,
            ref_max=it.ref_max,
            ref_range=it.ref_range
        )
        status = determine_item_status(norm_res["value"], norm_res["ref_min"], norm_res["ref_max"], it.status)
        status_label = "正常"
        if status == "HIGH":
            status_label = "偏高"
        elif status == "LOW":
            status_label = "偏低"
        elif status == "ABNORMAL":
            status_label = "异常"

        result.append({
            "code": canon,
            "raw_code": raw_code,
            "name": it.item_name or canon,
            "category": it.category or "other",
            "unit": std_unit,
            "latest_value": norm_res["value"],
            "raw_value": norm_res["raw_value"],
            "raw_unit": norm_res["raw_unit"],
            "is_converted": norm_res["is_converted"],
            "ref_min": norm_res["ref_min"],
            "ref_max": norm_res["ref_max"],
            "ref_range": norm_res["ref_range"] or it.ref_range or "",
            "status": status,
            "status_label": status_label,
            "latest_date": it.test_date or ""
        })
    return result

@router.get("/series")
def get_chart_series(
    codes: str = Query(..., description="以英文逗号分隔的指标代码，如 CEA,CA199 或 WBC,PLT"),
    target_user_id: int = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    根据指定指标代码集合，返回标准 ECharts 时序数据集（支持别名智能关联与医疗单位自动归一化）
    """
    user_id = target_user_id if (current_user.is_admin and target_user_id) else current_user.id
    code_list = [c.strip().upper() for c in codes.split(",") if c.strip()]
    if not code_list:
        return {"dates": [], "series": []}

    # 构建正向别名查询集合与反向映射
    query_codes = set()
    code_to_canonical = {}
    for req_c in code_list:
        matched_aliases = ALIAS_MAP.get(req_c, [req_c])
        for a in matched_aliases:
            query_codes.add(a)
            code_to_canonical[a] = req_c

    # 查询该用户所有相关的指标记录（过滤空日期与空数值），并按日期正序排列
    items = db.query(models.LabItem).filter(
        models.LabItem.user_id == user_id,
        models.LabItem.item_code.in_(list(query_codes)),
        models.LabItem.value != None,
        models.LabItem.test_date != None,
        models.LabItem.test_date != ""
    ).order_by(models.LabItem.test_date.asc()).all()

    # 提取所有不重复的采样日期
    dates = sorted(list({it.test_date for it in items if it.test_date}))

    # 构造每个指标的序列数据
    series_map = {}
    raw_vals_map = {}
    raw_units_map = {}
    converted_flags_map = {}
    info_map = {}

    for c in code_list:
        series_map[c] = {d: None for d in dates}
        raw_vals_map[c] = {d: None for d in dates}
        raw_units_map[c] = {d: None for d in dates}
        converted_flags_map[c] = {d: False for d in dates}

    for it in items:
        raw_c = (it.item_code or "").upper().strip()
        canon_c = code_to_canonical.get(raw_c, it.item_code)
        if canon_c in series_map:
            norm_res = normalize_lab_unit_and_value(
                item_code=canon_c,
                value=it.value,
                unit=it.unit,
                ref_min=it.ref_min,
                ref_max=it.ref_max,
                ref_range=it.ref_range
            )
            series_map[canon_c][it.test_date] = norm_res["value"]
            raw_vals_map[canon_c][it.test_date] = norm_res["raw_value"]
            raw_units_map[canon_c][it.test_date] = norm_res["raw_unit"]
            converted_flags_map[canon_c][it.test_date] = norm_res["is_converted"]

            if canon_c not in info_map:
                info_map[canon_c] = {
                    "name": it.item_name,
                    "unit": norm_res["unit"],
                    "ref_min": norm_res["ref_min"],
                    "ref_max": norm_res["ref_max"],
                    "ref_range": norm_res["ref_range"],
                    "category": it.category
                }
            elif norm_res["ref_max"] is not None and info_map[canon_c]["ref_max"] is None:
                info_map[canon_c]["ref_min"] = norm_res["ref_min"]
                info_map[canon_c]["ref_max"] = norm_res["ref_max"]
                info_map[canon_c]["ref_range"] = norm_res["ref_range"]

    series_data = []
    for c in code_list:
        if c in info_map:
            val_list = [series_map[c][d] for d in dates]
            raw_val_list = [raw_vals_map[c][d] for d in dates]
            raw_unit_list = [raw_units_map[c][d] for d in dates]
            converted_list = [converted_flags_map[c][d] for d in dates]
            series_data.append({
                "code": c,
                "name": info_map[c]["name"],
                "unit": info_map[c]["unit"],
                "ref_min": info_map[c]["ref_min"],
                "ref_max": info_map[c]["ref_max"],
                "ref_range": info_map[c]["ref_range"],
                "category": info_map[c]["category"],
                "data": val_list,
                "raw_values": raw_val_list,
                "raw_units": raw_unit_list,
                "converted_flags": converted_list
            })

    return {
        "dates": dates,
        "series": series_data
    }
