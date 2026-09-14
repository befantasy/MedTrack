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

@router.post("/reports", response_model=schemas.LabReportOut)
def create_lab_report(
    report_in: schemas.LabReportCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """手动或通过 AI 解析确认后新建化验单及检验明细项"""
    report = models.LabReport(
        user_id=current_user.id,
        report_type=report_in.report_type,
        report_date=report_in.report_date,
        hospital=report_in.hospital,
        raw_file_url=report_in.raw_file_url,
        ai_summary=report_in.ai_summary
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    for it in report_in.items:
        db_item = models.LabItem(
            report_id=report.id,
            user_id=current_user.id,
            item_name=it.item_name,
            item_code=it.item_code.upper().strip(),
            category=it.category,
            value=it.value,
            value_text=it.value_text or (str(it.value) if it.value is not None else ""),
            unit=it.unit,
            ref_min=it.ref_min,
            ref_max=it.ref_max,
            ref_range=it.ref_range,
            status=it.status or "NORMAL",
            test_date=report.report_date
        )
        db.add(db_item)

    db.commit()
    db.refresh(report)
    return report

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
