import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # 关系映射
    cancer_profile = relationship("CancerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    surgeries = relationship("Surgery", back_populates="user", cascade="all, delete-orphan", order_by="desc(Surgery.surgery_date)")
    radiotherapies = relationship("Radiotherapy", back_populates="user", cascade="all, delete-orphan", order_by="desc(Radiotherapy.start_date)")
    systemic_therapies = relationship("SystemicTherapy", back_populates="user", cascade="all, delete-orphan", order_by="desc(SystemicTherapy.start_date)")
    lab_reports = relationship("LabReport", back_populates="user", cascade="all, delete-orphan", order_by="desc(LabReport.report_date)")
    imaging_reports = relationship("ImagingReport", back_populates="user", cascade="all, delete-orphan", order_by="desc(ImagingReport.report_date)")
    pathology_reports = relationship("PathologyReport", back_populates="user", cascade="all, delete-orphan", order_by="desc(PathologyReport.report_date)")
    medical_records = relationship("MedicalRecord", back_populates="user", cascade="all, delete-orphan", order_by="desc(MedicalRecord.record_date)")
    share_links = relationship("ShareLink", back_populates="user", cascade="all, delete-orphan")


class CancerProfile(Base):
    """肿瘤专科与慢性病综合基准档案"""
    __tablename__ = "cancer_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    patient_name = Column(String(64), default="")
    gender = Column(String(16), default="")
    birth_date = Column(String(32), default="")
    
    # 肿瘤核心要素
    primary_site = Column(String(64), default="")          # 原发部位 (如：肺、胃、结直肠、乳腺等)
    pathology_type = Column(String(128), default="")       # 病理分型 (如：浸润性腺癌、鳞状细胞癌等)
    initial_diagnosis_date = Column(String(32), default="")# 初确诊日期
    initial_staging = Column(String(64), default="")       # 初诊分期 (如：cT2N2M0 IIIA期)
    current_staging = Column(String(64), default="")       # 当前治疗阶段/分期 (如：术后辅助/维持治疗/复发进展)
    molecular_markers = Column(Text, default="{}")         # 驱动基因与分子标志物 JSON (EGFR, ALK, KRAS, PD-L1等)
    
    # 伴随慢病与其他健康状况
    chronic_comorbidities = Column(Text, default="[]")     # 伴随慢病 JSON (高血压, 糖尿病, 冠心病等)
    allergies = Column(String(256), default="")            # 药物/食物过敏史
    ecog_score = Column(String(16), default="0")           # 体能状况评分 (ECOG 0-4)
    current_medications = Column(Text, default="[]")       # 当前日常服药清单 (含降压/降糖/保肝药)
    
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="cancer_profile")


class Surgery(Base):
    """手术治疗记录"""
    __tablename__ = "surgeries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    surgery_date = Column(String(32), nullable=False)
    surgery_name = Column(String(128), nullable=False)     # 术式名称 (如：胸腔镜下右肺下叶切除+淋巴结清扫)
    hospital = Column(String(128), default="")
    surgeon = Column(String(64), default="")
    margins = Column(String(32), default="R0")             # 切缘 (R0/R1/R2)
    lymph_nodes = Column(String(64), default="")           # 淋巴结清扫详情 (如：转移/清扫 2/18)
    pathology_summary = Column(Text, default="")           # 术后病理诊断总结
    complications = Column(String(256), default="")        # 术后并发症
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="surgeries")


class Radiotherapy(Base):
    """放疗记录"""
    __tablename__ = "radiotherapies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    site = Column(String(128), nullable=False)             # 照射部位/靶区 (如：纵隔引流区、颅脑病灶)
    technique = Column(String(64), default="")             # 放疗技术 (如：IMRT、SBRT、质子重离子)
    total_dose = Column(String(32), default="")            # 累积总剂量 (如：60 Gy)
    fractions = Column(String(32), default="")             # 分割次数 (如：30 F)
    start_date = Column(String(32), default="")
    end_date = Column(String(32), default="")
    hospital = Column(String(128), default="")
    toxicity_notes = Column(Text, default="")              # 急性/晚期放射反应
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="radiotherapies")


class SystemicTherapy(Base):
    """系统性药物治疗 (化疗、靶向、免疫、内分泌及联合方案周期)"""
    __tablename__ = "systemic_therapies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    treatment_line = Column(String(64), default="一线治疗")  # 辅助治疗 / 新辅助 / 一线 / 二线 / 维持治疗
    therapy_type = Column(String(64), default="靶向治疗")    # 化疗 / 靶向治疗 / 免疫治疗 / 联合方案 / 内分泌
    regimen_name = Column(String(128), nullable=False)     # 方案名称 (如：奥希替尼 80mg qd, 培美曲塞+顺铂)
    cycle_number = Column(Integer, default=1)              # 周期轮次
    start_date = Column(String(32), nullable=False)
    end_date = Column(String(32), default="")
    drugs_detail = Column(Text, default="[]")              # 用药明细与剂量 JSON
    adverse_events = Column(Text, default="[]")            # 毒副反应记录 (CTCAE 分级)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="systemic_therapies")


class LabReport(Base):
    """化验单总单 (血常规、生化、肿瘤标志物等)"""
    __tablename__ = "lab_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    report_type = Column(String(64), default="检验化验单")   # 肿瘤标志物 / 血常规 / 生化全套 / 甲功 等
    report_date = Column(String(32), nullable=False, index=True)
    hospital = Column(String(128), default="")
    raw_file_url = Column(String(256), default="")
    ai_summary = Column(Text, default="")                  # AI 归纳的异常提要
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="lab_reports")
    items = relationship("LabItem", back_populates="report", cascade="all, delete-orphan")


class LabItem(Base):
    """检验指标明细项 (用于时序绘图与异常监控)"""
    __tablename__ = "lab_items"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("lab_reports.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    item_name = Column(String(128), nullable=False)        # 中文项目名 (如 癌胚抗原, 白细胞, 空腹血糖)
    item_code = Column(String(64), nullable=False, index=True) # 标化缩写 (如 CEA, WBC, GLU, HbA1c, ALT, Cr)
    category = Column(String(32), default="other")         # tumor_marker, safety_toxicity, chronic, other
    value = Column(Float, nullable=True)                   # 数值形式 (供画图)
    value_text = Column(String(64), default="")            # 原始文本 (如 ">1000", "阴性(-)")
    unit = Column(String(32), default="")                  # 单位 (如 ng/mL, 10^9/L, mmol/L)
    ref_min = Column(Float, nullable=True)                 # 参考下限
    ref_max = Column(Float, nullable=True)                 # 参考上限
    ref_range = Column(String(64), default="")             # 参考区间文本 (如 0-5.0)
    status = Column(String(16), default="NORMAL")          # NORMAL, HIGH, LOW, ABNORMAL
    test_date = Column(String(32), nullable=False, index=True)

    report = relationship("LabReport", back_populates="items")


class ImagingReport(Base):
    """影像检查记录 (CT, MRI, PET-CT, 超声, 骨扫描)"""
    __tablename__ = "imaging_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    modality = Column(String(64), nullable=False)          # 检查方式 (胸腹部增强CT, 脑MRI, PET-CT)
    body_part = Column(String(64), default="")             # 部位
    report_date = Column(String(32), nullable=False, index=True)
    hospital = Column(String(128), default="")
    target_lesions = Column(Text, default="[]")            # 靶病灶尺寸追踪 JSON (如 [{"site": "右肺下叶", "size": "12mm x 9mm"}])
    recist_evaluation = Column(String(32), default="")     # RECIST评估 (CR完全缓解 / PR部分缓解 / SD稳定 / PD进展)
    findings = Column(Text, default="")                    # 检查所见
    impression = Column(Text, default="")                  # 影像诊断结论
    raw_file_url = Column(String(256), default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="imaging_reports")


class PathologyReport(Base):
    """病理与分子检测报告 (活检、术后病理、NGS基因检测)"""
    __tablename__ = "pathology_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    sample_type = Column(String(64), default="穿刺活检")    # 标本类型 (手术切除/穿刺活检/细胞学)
    sample_site = Column(String(64), default="")           # 取样部位
    report_date = Column(String(32), nullable=False, index=True)
    hospital = Column(String(128), default="")
    histological_diagnosis = Column(Text, default="")      # 组织学诊断 (如：肺腺癌)
    differentiation = Column(String(32), default="")       # 分化程度 (高/中/低分化)
    ihc_markers = Column(Text, default="{}")               # 免疫组化结果 JSON
    genetic_testing = Column(Text, default="{}")           # 基因检测结果 JSON
    raw_file_url = Column(String(256), default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="pathology_reports")


class MedicalRecord(Base):
    """日常症状随访与门诊记录"""
    __tablename__ = "medical_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    record_type = Column(String(32), default="symptom")    # symptom(症状/副反应), visit(门诊记录), note(备忘)
    title = Column(String(128), nullable=False)
    content = Column(Text, default="")
    record_date = Column(String(32), nullable=False, index=True)
    hospital = Column(String(128), default="")
    doctor = Column(String(64), default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="medical_records")


class ShareLink(Base):
    """门诊/MDT 就诊病历安全外链分享"""
    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    share_token = Column(String(64), unique=True, index=True, nullable=False)
    access_code = Column(String(16), default="")           # 可选 4 位访问提取码
    expires_at = Column(DateTime, nullable=False)          # 过期时间
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="share_links")
