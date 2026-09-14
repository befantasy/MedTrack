from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from datetime import datetime

# ==================== 用户与认证 ====================
class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool = False
    is_active: bool = True
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# ==================== 管理员与运维模型 ====================
class UserAdminDetail(BaseModel):
    id: int
    username: str
    is_admin: bool = False
    is_active: bool = True
    created_at: datetime
    patient_name: Optional[str] = ""
    primary_site: Optional[str] = ""
    pathology_type: Optional[str] = ""
    current_staging: Optional[str] = ""
    surgeries_count: int = 0
    radiotherapies_count: int = 0
    systemic_therapies_count: int = 0
    lab_reports_count: int = 0
    imaging_reports_count: int = 0
    model_config = ConfigDict(from_attributes=True)

class AdminUserCreate(BaseModel):
    username: str
    password: str
    is_admin: bool = False
    patient_name: Optional[str] = ""
    primary_site: Optional[str] = ""
    pathology_type: Optional[str] = ""

class AdminPasswordReset(BaseModel):
    new_password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class SystemSettingOut(BaseModel):
    key: str
    value: str
    description: Optional[str] = ""
    model_config = ConfigDict(from_attributes=True)

class SystemSettingUpdate(BaseModel):
    value: str

class AdminStatsOut(BaseModel):
    total_users: int
    active_users: int
    allow_registration: bool
    total_treatments: int
    total_labs: int
    total_imaging: int
    total_pathology: int
    uploads_size_bytes: int

# ==================== 肿瘤基准档案 ====================
class CancerProfileBase(BaseModel):
    patient_name: Optional[str] = ""
    gender: Optional[str] = ""
    birth_date: Optional[str] = ""
    primary_site: Optional[str] = ""
    pathology_type: Optional[str] = ""
    initial_diagnosis_date: Optional[str] = ""
    initial_staging: Optional[str] = ""
    current_staging: Optional[str] = ""
    molecular_markers: Optional[str] = "{}"
    chronic_comorbidities: Optional[str] = "[]"
    allergies: Optional[str] = ""
    ecog_score: Optional[str] = "0"
    current_medications: Optional[str] = "[]"

class CancerProfileCreate(CancerProfileBase):
    pass

class CancerProfileOut(CancerProfileBase):
    id: int
    user_id: int
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

# ==================== 手术记录 ====================
class SurgeryBase(BaseModel):
    surgery_date: str
    surgery_name: str
    hospital: Optional[str] = ""
    surgeon: Optional[str] = ""
    margins: Optional[str] = "R0"
    lymph_nodes: Optional[str] = ""
    pathology_summary: Optional[str] = ""
    complications: Optional[str] = ""

class SurgeryCreate(SurgeryBase):
    pass

class SurgeryUpdate(BaseModel):
    surgery_date: Optional[str] = None
    surgery_name: Optional[str] = None
    hospital: Optional[str] = None
    surgeon: Optional[str] = None
    margins: Optional[str] = None
    lymph_nodes: Optional[str] = None
    pathology_summary: Optional[str] = None
    complications: Optional[str] = None

class SurgeryOut(SurgeryBase):
    id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ==================== 放疗记录 ====================
class RadiotherapyBase(BaseModel):
    site: str
    technique: Optional[str] = ""
    total_dose: Optional[str] = ""
    fractions: Optional[str] = ""
    start_date: Optional[str] = ""
    end_date: Optional[str] = ""
    hospital: Optional[str] = ""
    toxicity_notes: Optional[str] = ""

class RadiotherapyCreate(RadiotherapyBase):
    pass

class RadiotherapyUpdate(BaseModel):
    site: Optional[str] = None
    technique: Optional[str] = None
    total_dose: Optional[str] = None
    fractions: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    hospital: Optional[str] = None
    toxicity_notes: Optional[str] = None

class RadiotherapyOut(RadiotherapyBase):
    id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ==================== 系统治疗记录 ====================
class SystemicTherapyBase(BaseModel):
    treatment_line: Optional[str] = "一线治疗"
    therapy_type: Optional[str] = "靶向治疗"
    regimen_name: str
    cycle_number: Optional[int] = 1
    start_date: str
    end_date: Optional[str] = ""
    drugs_detail: Optional[str] = "[]"
    adverse_events: Optional[str] = "[]"
    notes: Optional[str] = ""

class SystemicTherapyCreate(SystemicTherapyBase):
    pass

class SystemicTherapyUpdate(BaseModel):
    treatment_line: Optional[str] = None
    therapy_type: Optional[str] = None
    regimen_name: Optional[str] = None
    cycle_number: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    drugs_detail: Optional[str] = None
    adverse_events: Optional[str] = None
    notes: Optional[str] = None

class SystemicTherapyOut(SystemicTherapyBase):
    id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ==================== 化验单明细与总单 ====================
class LabItemBase(BaseModel):
    item_name: str
    item_code: str
    category: Optional[str] = "other"
    value: Optional[float] = None
    value_text: Optional[str] = ""
    unit: Optional[str] = ""
    ref_min: Optional[float] = None
    ref_max: Optional[float] = None
    ref_range: Optional[str] = ""
    status: Optional[str] = "NORMAL"
    test_date: str

class LabItemCreate(LabItemBase):
    pass

class LabItemOut(LabItemBase):
    id: int
    report_id: int
    model_config = ConfigDict(from_attributes=True)

class LabReportBase(BaseModel):
    report_type: Optional[str] = "检验化验单"
    report_date: str
    hospital: Optional[str] = ""
    raw_file_url: Optional[str] = ""
    ai_summary: Optional[str] = ""

class LabReportCreate(LabReportBase):
    items: List[LabItemCreate] = []

class LabReportOut(LabReportBase):
    id: int
    user_id: int
    created_at: datetime
    items: List[LabItemOut] = []
    model_config = ConfigDict(from_attributes=True)

# ==================== 影像检查报告 ====================
class ImagingReportBase(BaseModel):
    modality: str
    body_part: Optional[str] = ""
    report_date: str
    hospital: Optional[str] = ""
    target_lesions: Optional[str] = "[]"
    recist_evaluation: Optional[str] = ""
    findings: Optional[str] = ""
    impression: Optional[str] = ""
    raw_file_url: Optional[str] = ""

class ImagingReportCreate(ImagingReportBase):
    pass

class ImagingReportOut(ImagingReportBase):
    id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ==================== 病理报告 ====================
class PathologyReportBase(BaseModel):
    sample_type: Optional[str] = "穿刺活检"
    sample_site: Optional[str] = ""
    report_date: str
    hospital: Optional[str] = ""
    histological_diagnosis: Optional[str] = ""
    differentiation: Optional[str] = ""
    ihc_markers: Optional[str] = "{}"
    genetic_testing: Optional[str] = "{}"
    raw_file_url: Optional[str] = ""

class PathologyReportCreate(PathologyReportBase):
    pass

class PathologyReportOut(PathologyReportBase):
    id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ==================== 随访与日常记录 ====================
class MedicalRecordBase(BaseModel):
    record_type: Optional[str] = "symptom"
    title: str
    content: Optional[str] = ""
    record_date: str
    hospital: Optional[str] = ""
    doctor: Optional[str] = ""

class MedicalRecordCreate(MedicalRecordBase):
    pass

class MedicalRecordOut(MedicalRecordBase):
    id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ==================== 外链分享 ====================
class ShareLinkCreate(BaseModel):
    expire_days: int = 7
    access_code: Optional[str] = ""

class ShareLinkOut(BaseModel):
    share_token: str
    share_url: str
    access_code: Optional[str]
    expires_at: datetime

# ==================== 全病程时间轴综合事件 ====================
class TimelineEvent(BaseModel):
    id: str
    event_date: str
    event_type: str        # surgery, radio, therapy, imaging, lab, pathology, visit
    category_label: str    # 手术 / 放疗 / 系统治疗 / 影像复查 / 化验 / 病理 / 门诊
    title: str
    badge: Optional[str] = ""
    summary: str
    details: Optional[Dict[str, Any]] = None
