import os
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
import models
import schemas
from auth import hash_password, get_current_admin
from config import settings

router = APIRouter(prefix="/admin", tags=["超级管理与运维"])

def get_setting(db: Session, key: str, default: str = "") -> str:
    item = db.query(models.SystemSetting).filter(models.SystemSetting.key == key).first()
    return item.value if item else default

def set_setting(db: Session, key: str, value: str, description: str = ""):
    item = db.query(models.SystemSetting).filter(models.SystemSetting.key == key).first()
    if item:
        item.value = value
    else:
        item = models.SystemSetting(key=key, value=value, description=description)
        db.add(item)
    db.commit()

# ==================== 1. 系统概览与设置 ====================
@router.get("/stats", response_model=schemas.AdminStatsOut)
def get_system_stats(
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取系统数据概况与用量指标"""
    total_users = db.query(func.count(models.User.id)).scalar() or 0
    active_users = db.query(func.count(models.User.id)).filter(models.User.is_active == True).scalar() or 0
    
    allow_reg_str = get_setting(db, "allow_registration", "true").lower()
    allow_reg = allow_reg_str in ("true", "1", "yes")

    surgeries_c = db.query(func.count(models.Surgery.id)).scalar() or 0
    radios_c = db.query(func.count(models.Radiotherapy.id)).scalar() or 0
    chemos_c = db.query(func.count(models.SystemicTherapy.id)).scalar() or 0
    total_treatments = surgeries_c + radios_c + chemos_c

    total_labs = db.query(func.count(models.LabReport.id)).scalar() or 0
    total_imaging = db.query(func.count(models.ImagingReport.id)).scalar() or 0
    total_pathology = db.query(func.count(models.PathologyReport.id)).scalar() or 0

    # 统计上传附件目录物理大小
    uploads_size = 0
    if os.path.exists(settings.UPLOAD_DIR):
        for root, dirs, files in os.walk(settings.UPLOAD_DIR):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    uploads_size += os.path.getsize(fp)
                except Exception:
                    pass

    return {
        "total_users": total_users,
        "active_users": active_users,
        "allow_registration": allow_reg,
        "total_treatments": total_treatments,
        "total_labs": total_labs,
        "total_imaging": total_imaging,
        "total_pathology": total_pathology,
        "uploads_size_bytes": uploads_size
    }

@router.get("/settings")
def get_system_settings(
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取系统配置项列表"""
    allow_reg_str = get_setting(db, "allow_registration", "true")
    return {
        "allow_registration": allow_reg_str.lower() in ("true", "1", "yes")
    }

@router.put("/settings/registration")
def toggle_registration(
    data: schemas.SystemSettingUpdate,
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """开关普通用户自主注册通道"""
    val = "true" if data.value.lower() in ("true", "1", "yes") else "false"
    set_setting(db, "allow_registration", val, "允许新用户公开自主注册")
    return {"message": "注册开关已更新", "allow_registration": val == "true"}

@router.get("/settings/ai", response_model=schemas.AISettingOut)
def get_ai_settings(
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取 AI 大模型识别引擎配置（密钥脱敏显示）"""
    db_key = get_setting(db, "ai_api_key", "")
    key = db_key or settings.AI_API_KEY
    masked = ""
    if key and key != "your_api_key_here":
        if len(key) > 8:
            masked = key[:4] + "••••••••" + key[-4:]
        else:
            masked = "••••••••"

    db_base_url = get_setting(db, "ai_base_url", "")
    base_url = db_base_url or settings.AI_BASE_URL

    db_model = get_setting(db, "ai_model", "")
    model = db_model or settings.AI_MODEL

    return {
        "configured": bool(key and key != "your_api_key_here"),
        "masked_key": masked,
        "base_url": base_url,
        "model": model,
        "is_env_source": not bool(db_key)
    }

@router.put("/settings/ai")
def update_ai_settings(
    data: schemas.AISettingUpdate,
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新 AI 大模型配置（即时持久化到数据库生效）"""
    if data.api_key is not None and data.api_key.strip() != "":
        set_setting(db, "ai_api_key", data.api_key.strip(), "AI 大模型 API 密钥")
    if data.base_url is not None and data.base_url.strip() != "":
        set_setting(db, "ai_base_url", data.base_url.strip(), "AI 大模型 Base URL")
    if data.model is not None and data.model.strip() != "":
        set_setting(db, "ai_model", data.model.strip(), "AI 大模型 Model")
    return {"message": "AI 大模型识别引擎配置已成功保存并立即生效"}

# ==================== 2. 用户与租户管理 ====================
@router.get("/users", response_model=List[schemas.UserAdminDetail])
def list_users(
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员列出全平台所有用户及其病历总览"""
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    results = []
    for u in users:
        p = u.cancer_profile
        results.append({
            "id": u.id,
            "username": u.username,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "created_at": u.created_at,
            "patient_name": p.patient_name if p else "",
            "primary_site": p.primary_site if p else "",
            "pathology_type": p.pathology_type if p else "",
            "current_staging": p.current_staging if p else "",
            "surgeries_count": len(u.surgeries),
            "radiotherapies_count": len(u.radiotherapies),
            "systemic_therapies_count": len(u.systemic_therapies),
            "lab_reports_count": len(u.lab_reports),
            "imaging_reports_count": len(u.imaging_reports),
        })
    return results

@router.post("/users", response_model=schemas.UserOut)
def admin_create_user(
    data: schemas.AdminUserCreate,
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员手动开通新用户账号"""
    existing = db.query(models.User).filter(models.User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="该用户名已存在")
    
    hashed = hash_password(data.password)
    user = models.User(
        username=data.username,
        password_hash=hashed,
        is_admin=data.is_admin,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 创建初始患者基准档案
    profile = models.CancerProfile(
        user_id=user.id,
        patient_name=data.patient_name or data.username,
        primary_site=data.primary_site or "",
        pathology_type=data.pathology_type or "",
        current_staging="初诊评估中"
    )
    db.add(profile)
    db.commit()
    return user

@router.put("/users/{user_id}/status")
def toggle_user_active_status(
    user_id: int,
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """一键冻结/启用指定用户账号"""
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="不能冻结当前正在登录的管理员账号")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="目标用户不存在")
    
    user.is_active = not user.is_active
    db.commit()
    return {
        "message": f"用户状态已切换为: {'正常启用' if user.is_active else '已冻结'}",
        "user_id": user.id,
        "is_active": user.is_active
    }

@router.put("/users/{user_id}/password")
def admin_reset_password(
    user_id: int,
    data: schemas.AdminPasswordReset,
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员强制重置用户密码"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="目标用户不存在")
    
    if len(data.new_password) < 4:
        raise HTTPException(status_code=400, detail="新密码长度不能少于4位")
    
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": f"用户 [{user.username}] 的密码重置成功"}

@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: int,
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """彻底删除用户及其全部病历数据"""
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="不能删除自身管理员账号")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="目标用户不存在")
    
    username = user.username
    db.delete(user)
    db.commit()
    return {"message": f"用户 [{username}] 及其关联的全部病历记录已注销清除"}

# ==================== 3. 管理员查阅普通用户病历全宗 ====================
@router.get("/users/{user_id}/dossier")
def get_user_dossier(
    user_id: int,
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    核心功能：管理员无损调阅任意普通用户的全生命周期病历档案
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="患者用户不存在")

    p = user.cancer_profile
    profile_data = {
        "patient_name": p.patient_name if p else "",
        "gender": p.gender if p else "",
        "birth_date": p.birth_date if p else "",
        "primary_site": p.primary_site if p else "",
        "pathology_type": p.pathology_type if p else "",
        "initial_diagnosis_date": p.initial_diagnosis_date if p else "",
        "initial_staging": p.initial_staging if p else "",
        "current_staging": p.current_staging if p else "",
        "molecular_markers": p.molecular_markers if p else "{}",
        "chronic_comorbidities": p.chronic_comorbidities if p else "[]",
        "allergies": p.allergies if p else "",
        "ecog_score": p.ecog_score if p else "0",
        "current_medications": p.current_medications if p else "[]"
    } if p else {}

    # 化验单与指标
    # 化验单与指标
    labs_data = []
    for l in user.lab_reports:
        items = [{
            "item_name": item.item_name,
            "item_code": item.item_code,
            "value": item.value,
            "value_text": item.value_text,
            "unit": item.unit,
            "ref_range": item.ref_range,
            "status": item.status,
            "category": item.category
        } for item in l.items]
        labs_data.append({
            "id": l.id,
            "report_date": l.report_date,
            "report_type": l.report_type,
            "hospital": l.hospital,
            "ai_summary": l.ai_summary,
            "items": items
        })

    # 影像复查
    imaging_data = [{
        "id": img.id,
        "report_date": img.report_date,
        "modality": img.modality,
        "body_part": img.body_part,
        "findings": img.findings,
        "impression": img.impression,
        "recist_evaluation": img.recist_evaluation,
        "hospital": img.hospital
    } for img in user.imaging_reports]

    # 病理报告
    pathology_data = [{
        "id": path.id,
        "report_date": path.report_date,
        "sample_type": path.sample_type,
        "sample_site": path.sample_site,
        "differentiation": path.differentiation,
        "histological_diagnosis": path.histological_diagnosis,
        "ihc_markers": path.ihc_markers,
        "genetic_testing": path.genetic_testing,
        "hospital": path.hospital
    } for path in user.pathology_reports]

    # 手术
    surgeries_data = [{
        "id": s.id,
        "surgery_date": s.surgery_date,
        "surgery_name": s.surgery_name,
        "hospital": s.hospital,
        "surgeon": s.surgeon,
        "margins": s.margins,
        "lymph_nodes": s.lymph_nodes,
        "pathology_summary": s.pathology_summary
    } for s in user.surgeries]

    # 放疗
    radiotherapies_data = [{
        "id": r.id,
        "start_date": r.start_date,
        "end_date": r.end_date,
        "site": r.site,
        "technique": r.technique,
        "total_dose": r.total_dose,
        "fractions": r.fractions,
        "toxicity_notes": r.toxicity_notes,
        "hospital": r.hospital
    } for r in user.radiotherapies]

    # 系统治疗 (化疗/靶向/免疫)
    systemic_data = [{
        "id": st.id,
        "start_date": st.start_date,
        "end_date": st.end_date,
        "treatment_line": st.treatment_line,
        "therapy_type": st.therapy_type,
        "regimen_name": st.regimen_name,
        "cycle_number": st.cycle_number,
        "drugs_detail": st.drugs_detail,
        "adverse_events": st.adverse_events
    } for st in user.systemic_therapies]

    # 门诊就诊与随访随记
    records_data = [{
        "id": mr.id,
        "record_date": mr.record_date,
        "record_type": mr.record_type,
        "title": mr.title,
        "content": mr.content,
        "hospital": mr.hospital,
        "doctor": mr.doctor
    } for mr in user.medical_records]

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat() if user.created_at else None
        },
        "profile": profile_data,
        "surgeries": surgeries_data,
        "radiotherapies": radiotherapies_data,
        "systemic_therapies": systemic_data,
        "lab_reports": labs_data,
        "imaging_reports": imaging_data,
        "pathology_reports": pathology_data,
        "medical_records": records_data
    }
