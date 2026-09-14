from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import get_current_user

router = APIRouter(prefix="/imagings", tags=["影像检查报告管理"])

@router.get("/reports", response_model=List[schemas.ImagingReportOut])
def get_imaging_reports(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户所有影像复查报告 (CT, MRI, PET-CT, 超声)"""
    return db.query(models.ImagingReport).filter(
        models.ImagingReport.user_id == current_user.id
    ).order_by(models.ImagingReport.report_date.desc()).all()

@router.post("/reports", response_model=schemas.ImagingReportOut)
def create_imaging_report(
    report_in: schemas.ImagingReportCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """保存影像检查报告"""
    try:
        report = models.ImagingReport(
            **report_in.model_dump(),
            user_id=current_user.id
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report
    except Exception as e:
        import logging
        logging.exception("Failed to create imaging report")
        raise HTTPException(status_code=400, detail=f"内部保存失败: {str(e)}")

@router.put("/reports/{id}", response_model=schemas.ImagingReportOut)
def update_imaging_report(
    id: int,
    data_in: schemas.ImagingReportUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    report = db.query(models.ImagingReport).filter(
        models.ImagingReport.id == id,
        models.ImagingReport.user_id == current_user.id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="影像报告不存在")
        
    update_data = data_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(report, key, value)
        
    db.commit()
    db.refresh(report)
    return report

@router.delete("/reports/{id}")
def delete_imaging_report(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除影像检查报告"""
    report = db.query(models.ImagingReport).filter(
        models.ImagingReport.id == id,
        models.ImagingReport.user_id == current_user.id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="影像报告不存在")
    db.delete(report)
    db.commit()
    return {"message": "影像报告删除成功"}
