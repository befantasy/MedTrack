from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
import models
from auth import get_current_user

router = APIRouter(prefix="/charts", tags=["指标趋势图表数据"])

@router.get("/available-metrics")
def get_available_metrics(
    target_user_id: int = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取指定用户所有已记录的指标清单"""
    user_id = target_user_id if (current_user.is_admin and target_user_id) else current_user.id
    items = db.query(
        models.LabItem.item_code,
        models.LabItem.item_name,
        models.LabItem.category,
        models.LabItem.unit
    ).filter(
        models.LabItem.user_id == user_id
    ).distinct().all()

    result = []
    for it in items:
        result.append({
            "code": it.item_code,
            "name": it.item_name,
            "category": it.category,
            "unit": it.unit
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
    根据指定指标代码集合，返回标准 ECharts 时序数据集
    """
    user_id = target_user_id if (current_user.is_admin and target_user_id) else current_user.id
    code_list = [c.strip().upper() for c in codes.split(",") if c.strip()]
    if not code_list:
        return {"dates": [], "series": []}

    # 查询该用户所有相关的指标记录并按日期正序排列
    items = db.query(models.LabItem).filter(
        models.LabItem.user_id == user_id,
        models.LabItem.item_code.in_(code_list),
        models.LabItem.value != None
    ).order_by(models.LabItem.test_date.asc()).all()

    # 提取所有不重复的采样日期
    dates = sorted(list({it.test_date for it in items}))

    # 构造每个指标的序列数据
    series_map = {}
    info_map = {}

    for c in code_list:
        series_map[c] = {d: None for d in dates}

    for it in items:
        c = it.item_code
        if c in series_map:
            series_map[c][it.test_date] = it.value
            if c not in info_map:
                info_map[c] = {
                    "name": it.item_name,
                    "unit": it.unit,
                    "ref_min": it.ref_min,
                    "ref_max": it.ref_max,
                    "ref_range": it.ref_range,
                    "category": it.category
                }

    series_data = []
    for c in code_list:
        if c in info_map:
            val_list = [series_map[c][d] for d in dates]
            series_data.append({
                "code": c,
                "name": info_map[c]["name"],
                "unit": info_map[c]["unit"],
                "ref_min": info_map[c]["ref_min"],
                "ref_max": info_map[c]["ref_max"],
                "ref_range": info_map[c]["ref_range"],
                "category": info_map[c]["category"],
                "data": val_list
            })

    return {
        "dates": dates,
        "series": series_data
    }
