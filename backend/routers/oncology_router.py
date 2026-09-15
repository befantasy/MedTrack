from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import get_current_user

router = APIRouter(prefix="/oncology", tags=["肿瘤治疗全流程管理"])

# ==================== 手术记录 ====================
@router.get("/surgeries", response_model=List[schemas.SurgeryOut])
def get_surgeries(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Surgery).filter(models.Surgery.user_id == current_user.id).order_by(models.Surgery.surgery_date.desc()).all()

@router.post("/surgeries", response_model=schemas.SurgeryOut)
def create_surgery(data_in: schemas.SurgeryCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = models.Surgery(**data_in.model_dump(), user_id=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.put("/surgeries/{id}", response_model=schemas.SurgeryOut)
def update_surgery(id: int, data_in: schemas.SurgeryUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.Surgery).filter(models.Surgery.id == id, models.Surgery.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="手术记录未找到")
    for key, val in data_in.model_dump(exclude_unset=True).items():
        setattr(item, key, val)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/surgeries/{id}")
def delete_surgery(id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.Surgery).filter(models.Surgery.id == id, models.Surgery.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="手术记录未找到")
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}

# ==================== 放疗记录 ====================
@router.get("/radiotherapies", response_model=List[schemas.RadiotherapyOut])
def get_radiotherapies(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Radiotherapy).filter(models.Radiotherapy.user_id == current_user.id).order_by(models.Radiotherapy.start_date.desc()).all()

@router.post("/radiotherapies", response_model=schemas.RadiotherapyOut)
def create_radiotherapy(data_in: schemas.RadiotherapyCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = models.Radiotherapy(**data_in.model_dump(), user_id=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.put("/radiotherapies/{id}", response_model=schemas.RadiotherapyOut)
def update_radiotherapy(id: int, data_in: schemas.RadiotherapyUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.Radiotherapy).filter(models.Radiotherapy.id == id, models.Radiotherapy.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="放疗记录未找到")
    for key, val in data_in.model_dump(exclude_unset=True).items():
        setattr(item, key, val)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/radiotherapies/{id}")
def delete_radiotherapy(id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.Radiotherapy).filter(models.Radiotherapy.id == id, models.Radiotherapy.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="放疗记录未找到")
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}

# ==================== 系统治疗记录 (化疗/靶向/免疫/内分泌) ====================
@router.get("/therapies", response_model=List[schemas.SystemicTherapyOut])
def get_therapies(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.SystemicTherapy).filter(models.SystemicTherapy.user_id == current_user.id).order_by(models.SystemicTherapy.start_date.desc()).all()

@router.post("/therapies", response_model=schemas.SystemicTherapyOut)
def create_therapy(data_in: schemas.SystemicTherapyCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = models.SystemicTherapy(**data_in.model_dump(), user_id=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.put("/therapies/{id}", response_model=schemas.SystemicTherapyOut)
def update_therapy(id: int, data_in: schemas.SystemicTherapyUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.SystemicTherapy).filter(models.SystemicTherapy.id == id, models.SystemicTherapy.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="治疗记录未找到")
    for key, val in data_in.model_dump(exclude_unset=True).items():
        setattr(item, key, val)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/therapies/{id}")
def delete_therapy(id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.SystemicTherapy).filter(models.SystemicTherapy.id == id, models.SystemicTherapy.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="治疗记录未找到")
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}

# ==================== 病理与分子检测 ====================
@router.get("/pathologies", response_model=List[schemas.PathologyReportOut])
def get_pathologies(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.PathologyReport).filter(models.PathologyReport.user_id == current_user.id).order_by(models.PathologyReport.report_date.desc()).all()

@router.post("/pathologies", response_model=schemas.PathologyReportOut)
def create_pathology(data_in: schemas.PathologyReportCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        item = models.PathologyReport(**data_in.model_dump(), user_id=current_user.id)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    except Exception as e:
        import logging
        logging.exception("Failed to create pathology report")
        raise HTTPException(status_code=400, detail=f"内部保存失败: {str(e)}")

@router.put("/pathologies/{id}", response_model=schemas.PathologyReportOut)
def update_pathology(
    id: int, 
    data_in: schemas.PathologyReportUpdate, 
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    item = db.query(models.PathologyReport).filter(
        models.PathologyReport.id == id, 
        models.PathologyReport.user_id == current_user.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    update_data = data_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
        
    db.commit()
    db.refresh(item)
    return item

@router.delete("/pathologies/{id}")
def delete_pathology(id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.PathologyReport).filter(models.PathologyReport.id == id, models.PathologyReport.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="病理记录未找到")
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}

# ==================== 门诊与日常随访 ====================
@router.get("/records", response_model=List[schemas.MedicalRecordOut])
def get_medical_records(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.MedicalRecord).filter(models.MedicalRecord.user_id == current_user.id).order_by(models.MedicalRecord.record_date.desc()).all()

@router.post("/records", response_model=schemas.MedicalRecordOut)
def create_medical_record(data_in: schemas.MedicalRecordCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = models.MedicalRecord(**data_in.model_dump(), user_id=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/records/{id}")
def delete_medical_record(id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.MedicalRecord).filter(models.MedicalRecord.id == id, models.MedicalRecord.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="随访记录未找到")
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}

# ==================== 全病程治疗全景时间轴 (Swimlane Timeline) ====================
@router.get("/timeline", response_model=List[schemas.TimelineEvent])
def get_full_timeline(
    target_user_id: int = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """聚合患者所有医疗事件并按日期降序排列，供给前端泳道时间轴渲染"""
    user_id = target_user_id if (current_user.is_admin and target_user_id) else current_user.id
    events: List[schemas.TimelineEvent] = []
    
    # 1. 手术
    for s in db.query(models.Surgery).filter(models.Surgery.user_id == user_id).all():
        events.append(schemas.TimelineEvent(
            id=f"surgery_{s.id}",
            event_date=s.surgery_date,
            event_type="surgery",
            category_label="外科手术",
            title=s.surgery_name,
            badge=f"切缘 {s.margins}" if s.margins else "手术",
            summary=f"淋巴结: {s.lymph_nodes or '未详'} | 医院: {s.hospital or '本院'}",
            details={"surgeon": s.surgeon, "pathology": s.pathology_summary, "complications": s.complications}
        ))

    # 2. 放疗
    for r in db.query(models.Radiotherapy).filter(models.Radiotherapy.user_id == user_id).all():
        events.append(schemas.TimelineEvent(
            id=f"radio_{r.id}",
            event_date=r.start_date,
            event_type="radio",
            category_label="放射治疗",
            title=f"放疗: {r.site}",
            badge=f"{r.total_dose} / {r.fractions}" if r.total_dose else "放疗",
            summary=f"技术: {r.technique or '标准'} | 周期: {r.start_date} ~ {r.end_date or '持续'}",
            details={"toxicity": r.toxicity_notes, "hospital": r.hospital}
        ))

    # 3. 系统药物治疗
    for t in db.query(models.SystemicTherapy).filter(models.SystemicTherapy.user_id == user_id).all():
        events.append(schemas.TimelineEvent(
            id=f"therapy_{t.id}",
            event_date=t.start_date,
            event_type="therapy",
            category_label=t.therapy_type or "系统用药",
            title=f"{t.regimen_name} (第 {t.cycle_number} 周期)",
            badge=t.treatment_line or "治疗",
            summary=f"周期: {t.start_date} ~ {t.end_date or '今'}",
            details={"drugs": t.drugs_detail, "adverse": t.adverse_events, "notes": t.notes}
        ))

    # 4. 影像复查
    for img in db.query(models.ImagingReport).filter(models.ImagingReport.user_id == user_id).all():
        events.append(schemas.TimelineEvent(
            id=f"imaging_{img.id}",
            event_date=img.report_date,
            event_type="imaging",
            category_label="影像复查",
            title=f"{img.modality} ({img.body_part or '部位未注'})",
            badge=img.recist_evaluation or "复查",
            summary=img.impression[:80] + ("..." if len(img.impression) > 80 else "") if img.impression else "影像报告",
            details={
                "hospital": img.hospital,
                "modality": img.modality,
                "body_part": img.body_part,
                "findings": img.findings,
                "impression": img.impression,
                "target_lesions": img.target_lesions,
                "raw_file_url": img.raw_file_url
            }
        ))

    # 5. 化验检验
    for lab in db.query(models.LabReport).filter(models.LabReport.user_id == user_id).all():
        item_count = len(lab.items)
        abnormal_items = [it.item_code for it in lab.items if it.status in ("HIGH", "LOW", "ABNORMAL")]
        badge_text = f"{len(abnormal_items)}项异常" if abnormal_items else "指标平稳"
        items_data = [
            {
                "name": it.item_name,
                "code": it.item_code,
                "value": it.value,
                "value_text": it.value_text or (str(it.value) if it.value is not None else ""),
                "unit": it.unit,
                "ref_range": it.ref_range,
                "status": it.status
            }
            for it in lab.items
        ]
        events.append(schemas.TimelineEvent(
            id=f"lab_{lab.id}",
            event_date=lab.report_date,
            event_type="lab",
            category_label="化验检验",
            title=lab.report_type or "化验单",
            badge=badge_text,
            summary=lab.ai_summary or f"共包含 {item_count} 项检验指标",
            details={
                "hospital": lab.hospital,
                "abnormal_codes": abnormal_items,
                "items": items_data,
                "raw_file_url": lab.raw_file_url
            }
        ))

    # 6. 病理报告
    for p in db.query(models.PathologyReport).filter(models.PathologyReport.user_id == user_id).all():
        events.append(schemas.TimelineEvent(
            id=f"pathology_{p.id}",
            event_date=p.report_date,
            event_type="pathology",
            category_label="病理/基因",
            title=f"病理: {p.sample_site or p.sample_type or '标本'}",
            badge=p.differentiation or "病理",
            summary=p.histological_diagnosis[:80] if p.histological_diagnosis else "病理检查报告",
            details={
                "sample_type": p.sample_type,
                "sample_site": p.sample_site,
                "histological_diagnosis": p.histological_diagnosis,
                "ihc": p.ihc_markers,
                "gene": p.genetic_testing,
                "raw_file_url": p.raw_file_url
            }
        ))

    # 7. 门诊随访与症状记录
    for m in db.query(models.MedicalRecord).filter(models.MedicalRecord.user_id == user_id).all():
        events.append(schemas.TimelineEvent(
            id=f"record_{m.id}",
            event_date=m.record_date,
            event_type="visit",
            category_label="随访/门诊" if m.record_type == "visit" else "症状记录",
            title=m.title,
            badge=m.doctor or "记录",
            summary=m.content[:80] if m.content else "",
            details={"hospital": m.hospital, "doctor": m.doctor}
        ))

    # 按时间降序排序
    events.sort(key=lambda x: x.event_date, reverse=True)
    return events
