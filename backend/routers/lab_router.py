from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import get_current_user

router = APIRouter(prefix="/labs", tags=["化验单与指标管理"])

@router.get("/reports", response_model=List[schemas.LabReportOut])
def get_lab_reports(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的所有化验单列表"""
    return db.query(models.LabReport).filter(
        models.LabReport.user_id == current_user.id
    ).order_by(models.LabReport.report_date.desc()).all()

def normalize_lab_code(code: str) -> str:
    c = (code or "OTHER").upper().strip()
    # 常用医学指标英文字母别名归一化
    if c in ("CA19-9", "CA-199", "糖类抗原199", "糖类抗原19-9"):
        return "CA199"
    if c in ("CA-125", "糖类抗原125"):
        return "CA125"
    if c in ("CA-153", "CA15-3", "糖类抗原153"):
        return "CA153"
    if c in ("CYFRA211", "CYFRA 21-1"):
        return "CYFRA21-1"
    if c in ("CREA", "CRE", "血肌酐", "肌酐"):
        return "CR"
    if c in ("NEUT", "中性粒细胞", "中性粒细胞绝对值"):
        return "NEUT#"
    if c in ("GPT", "谷丙转氨酶"):
        return "ALT"
    if c in ("GOT", "谷草转氨酶"):
        return "AST"
    if c in ("GLUCOSE", "血糖", "空腹血糖"):
        return "GLU"
    if c in ("UA", "URIC", "尿酸"):
        return "UA"
    return c

@router.post("/reports", response_model=schemas.LabReportOut)
def create_lab_report(
    report_in: schemas.LabReportCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import logging
    try:
        """手动或通过 AI 解析确认后新建化验单及检验明细项"""
        report = models.LabReport(
            user_id=current_user.id,
            report_type=report_in.report_type or "检验化验单",
            report_date=report_in.report_date,
            hospital=report_in.hospital or "",
            raw_file_url=report_in.raw_file_url or "",
            ai_summary=report_in.ai_summary or ""
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        for it in report_in.items:
            code = normalize_lab_code(it.item_code)
            db_item = models.LabItem(
                report_id=report.id,
                user_id=current_user.id,
                item_name=it.item_name or code,
                item_code=code,
                category=it.category or "other",
                value=it.value,
                value_text=it.value_text or (str(it.value) if it.value is not None else ""),
                unit=it.unit or "",
                ref_min=it.ref_min,
                ref_max=it.ref_max,
                ref_range=it.ref_range or "",
                status=it.status or "NORMAL",
                test_date=it.test_date or report.report_date
            )
            db.add(db_item)

        db.commit()
        db.refresh(report)
        return report
    except Exception as e:
        logging.exception("Failed to create lab report")
        raise HTTPException(status_code=400, detail=f"内部保存失败: {str(e)}")

@router.get("/reports/{id}", response_model=schemas.LabReportOut)
def get_lab_report(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取特定化验单详细信息及所有指标"""
    report = db.query(models.LabReport).filter(
        models.LabReport.id == id,
        models.LabReport.user_id == current_user.id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="化验单不存在")
    return report

@router.put("/reports/{id}", response_model=schemas.LabReportOut)
def update_lab_report(
    id: int,
    data_in: schemas.LabReportUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    report = db.query(models.LabReport).filter(
        models.LabReport.id == id,
        models.LabReport.user_id == current_user.id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="化验单不存在")

    update_data = data_in.model_dump(exclude_unset=True)
    items_in = update_data.pop("items", None)

    for key, value in update_data.items():
        setattr(report, key, value)
    
    if items_in is not None:
        db.query(models.LabItem).filter(models.LabItem.report_id == id).delete()
        for it in items_in:
            db_it = models.LabItem(**it, report_id=id)
            db.add(db_it)

    db.commit()
    db.refresh(report)
    return report

@router.delete("/reports/{id}")
def delete_lab_report(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除化验单及关联的指标数据"""
    report = db.query(models.LabReport).filter(
        models.LabReport.id == id,
        models.LabReport.user_id == current_user.id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="化验单不存在")
    db.delete(report)
    db.commit()
    return {"message": "化验单删除成功"}
