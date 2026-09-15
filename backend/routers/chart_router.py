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

@router.get("/available-metrics")
def get_available_metrics(
    target_user_id: int = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取指定用户所有已记录的指标清单（智能去重与基准单位对齐）"""
    user_id = target_user_id if (current_user.is_admin and target_user_id) else current_user.id
    items = db.query(
        models.LabItem.item_code,
        models.LabItem.item_name,
        models.LabItem.category,
        models.LabItem.unit
    ).filter(
        models.LabItem.user_id == user_id,
        models.LabItem.item_code != None,
        models.LabItem.item_code != ""
    ).distinct().all()

    result = []
    seen = set()
    for it in items:
        raw_code = it.item_code.strip()
        code_upper = raw_code.upper()
        canon = CANONICAL_MAP.get(code_upper, code_upper)
        if canon in seen:
            continue
        seen.add(canon)
        std_unit = STANDARD_UNITS.get(canon, it.unit or "")
        result.append({
            "code": canon,
            "raw_code": raw_code,
            "name": it.item_name or canon,
            "category": it.category or "other",
            "unit": std_unit
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
