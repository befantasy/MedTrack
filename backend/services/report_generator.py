import json
from typing import Dict, Any, List
from sqlalchemy.orm import Session
import models

class ReportGeneratorService:
    """肿瘤全病程 MDT 多学科门诊就诊报告生成引擎"""

    def generate_consultation_report(self, user_id: int, db: Session) -> Dict[str, Any]:
        """聚合患者全生命周期病史，生成医生接诊格式的完整结构化摘要"""
        
        # 1. 获取基准档案
        profile = db.query(models.CancerProfile).filter(models.CancerProfile.user_id == user_id).first()
        
        # 2. 获取手术史
        surgeries = db.query(models.Surgery).filter(models.Surgery.user_id == user_id).order_by(models.Surgery.surgery_date.desc()).all()
        
        # 3. 获取放疗史
        radios = db.query(models.Radiotherapy).filter(models.Radiotherapy.user_id == user_id).order_by(models.Radiotherapy.start_date.desc()).all()
        
        # 4. 获取系统治疗史 (化疗/靶向/免疫)
        therapies = db.query(models.SystemicTherapy).filter(models.SystemicTherapy.user_id == user_id).order_by(models.SystemicTherapy.start_date.desc()).all()
        
        # 5. 获取最新 3 次影像检查
        imagings = db.query(models.ImagingReport).filter(models.ImagingReport.user_id == user_id).order_by(models.ImagingReport.report_date.desc()).limit(3).all()
        
        # 6. 获取病理与分子报告
        pathologies = db.query(models.PathologyReport).filter(models.PathologyReport.user_id == user_id).order_by(models.PathologyReport.report_date.desc()).all()
        
        # 7. 获取最近化验单与高频指标演变 (取近 4 个采样日期的核心指标做横向对比)
        lab_dates_query = db.query(models.LabItem.test_date).filter(models.LabItem.user_id == user_id).distinct().order_by(models.LabItem.test_date.desc()).limit(4).all()
        recent_dates = [d[0] for d in lab_dates_query]
        recent_dates.reverse() # 正序排列 便于看趋势
        
        # 提取核心跟踪指标
        key_indicator_codes = ["CEA", "CA199", "CA125", "AFP", "WBC", "PLT", "NEUT#", "ALT", "Cr", "GLU"]
        indicator_comparison = []
        
        for code in key_indicator_codes:
            items = db.query(models.LabItem).filter(
                models.LabItem.user_id == user_id,
                models.LabItem.item_code == code,
                models.LabItem.test_date.in_(recent_dates)
            ).all()
            if items:
                date_map = {item.test_date: item for item in items}
                unit = items[0].unit
                ref_range = items[0].ref_range or f"{items[0].ref_min}-{items[0].ref_max}"
                row = {
                    "code": code,
                    "name": items[0].item_name,
                    "category": items[0].category,
                    "unit": unit,
                    "ref_range": ref_range,
                    "values": [
                        {
                            "date": d,
                            "val": date_map[d].value if d in date_map else None,
                            "val_text": date_map[d].value_text if d in date_map else "-",
                            "status": date_map[d].status if d in date_map else "NORMAL"
                        } for d in recent_dates
                    ]
                }
                indicator_comparison.append(row)

        # 解析 JSON 字段
        markers_parsed = {}
        comorbidities_parsed = []
        medications_parsed = []
        if profile:
            try:
                markers_parsed = json.loads(profile.molecular_markers) if profile.molecular_markers else {}
            except Exception:
                markers_parsed = {}
            try:
                comorbidities_parsed = json.loads(profile.chronic_comorbidities) if profile.chronic_comorbidities else []
            except Exception:
                comorbidities_parsed = []
            try:
                medications_parsed = json.loads(profile.current_medications) if profile.current_medications else []
            except Exception:
                medications_parsed = []

        # 整理生成完整报告字典
        report = {
            "generated_at": str(models.datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")),
            "profile": {
                "name": profile.patient_name if profile else "患者",
                "gender": profile.gender if profile else "",
                "birth_date": profile.birth_date if profile else "",
                "primary_site": profile.primary_site if profile else "未录入",
                "pathology_type": profile.pathology_type if profile else "未录入",
                "initial_staging": profile.initial_staging if profile else "",
                "current_staging": profile.current_staging if profile else "",
                "ecog_score": profile.ecog_score if profile else "0",
                "molecular_markers": markers_parsed,
                "chronic_comorbidities": comorbidities_parsed,
                "current_medications": medications_parsed,
                "allergies": profile.allergies if profile else "无明确记录"
            },
            "treatment_summary": {
                "has_surgery": len(surgeries) > 0,
                "surgeries": [
                    {
                        "date": s.surgery_date,
                        "name": s.surgery_name,
                        "hospital": s.hospital,
                        "surgeon": s.surgeon,
                        "margins": s.margins,
                        "lymph_nodes": s.lymph_nodes,
                        "summary": s.pathology_summary
                    } for s in surgeries
                ],
                "has_radiotherapy": len(radios) > 0,
                "radiotherapies": [
                    {
                        "site": r.site,
                        "technique": r.technique,
                        "dose": r.total_dose,
                        "fractions": r.fractions,
                        "date": f"{r.start_date} ~ {r.end_date}" if r.end_date else r.start_date,
                        "toxicity": r.toxicity_notes
                    } for r in radios
                ],
                "has_systemic_therapy": len(therapies) > 0,
                "systemic_therapies": [
                    {
                        "line": t.treatment_line,
                        "type": t.therapy_type,
                        "regimen": t.regimen_name,
                        "cycle": f"第 {t.cycle_number} 周期",
                        "date": f"{t.start_date} ~ {t.end_date}" if t.end_date else t.start_date,
                        "adverse_events": t.adverse_events
                    } for t in therapies
                ]
            },
            "latest_imaging": [
                {
                    "date": img.report_date,
                    "modality": img.modality,
                    "body_part": img.body_part,
                    "recist": img.recist_evaluation or "未注",
                    "impression": img.impression,
                    "findings": img.findings
                } for img in imagings
            ],
            "pathologies": [
                {
                    "date": p.report_date,
                    "sample": f"{p.sample_site} {p.sample_type}",
                    "diagnosis": p.histological_diagnosis,
                    "ihc": p.ihc_markers,
                    "gene": p.genetic_testing
                } for p in pathologies
            ],
            "lab_trend_comparison": {
                "dates": recent_dates,
                "indicators": indicator_comparison
            }
        }
        return report

report_generator = ReportGeneratorService()
