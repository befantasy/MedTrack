import json
from typing import Dict, Any, List
from sqlalchemy.orm import Session
import models
from services.unit_converter import normalize_lab_unit_and_value

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
        
        # 7. 获取最近保存的化验单记录 (展示全貌与 AI 总结)
        lab_reports_db = db.query(models.LabReport).filter(
            models.LabReport.user_id == user_id
        ).order_by(models.LabReport.report_date.desc()).limit(5).all()
        
        # 8. 获取有效采样日期 (取近 6 个采样日期做横向对比)
        lab_dates_query = db.query(models.LabItem.test_date).filter(
            models.LabItem.user_id == user_id,
            models.LabItem.test_date != None,
            models.LabItem.test_date != ""
        ).distinct().order_by(models.LabItem.test_date.desc()).limit(6).all()
        recent_dates = [d[0] for d in lab_dates_query if d[0]]
        recent_dates.reverse() # 正序排列 便于看演变趋势

        # 别名归一化映射表
        def get_canonical_code(raw_code: str) -> str:
            c = (raw_code or "").upper().strip()
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

        # 动态获取患者在这些日期内所有实际存在的指标 (支持动态展现用户上传的任意化验指标)
        items_in_dates = db.query(models.LabItem).filter(
            models.LabItem.user_id == user_id,
            models.LabItem.test_date.in_(recent_dates)
        ).all()

        indicator_groups = {}
        for it in items_in_dates:
            canon = get_canonical_code(it.item_code)
            norm_res = normalize_lab_unit_and_value(
                item_code=canon,
                value=it.value,
                unit=it.unit,
                ref_min=it.ref_min,
                ref_max=it.ref_max,
                ref_range=it.ref_range
            )
            if canon not in indicator_groups:
                indicator_groups[canon] = {
                    "code": it.item_code,
                    "name": it.item_name or it.item_code,
                    "category": it.category or "other",
                    "unit": norm_res["unit"] or it.unit or "",
                    "ref_range": norm_res["ref_range"] or it.ref_range or (f"{it.ref_min}-{it.ref_max}" if it.ref_min is not None and it.ref_max is not None else ""),
                    "has_abnormal": False,
                    "date_map": {}
                }
            if it.status in ("HIGH", "LOW", "ABNORMAL"):
                indicator_groups[canon]["has_abnormal"] = True
            
            indicator_groups[canon]["date_map"][it.test_date] = {
                "val": norm_res["value"],
                "val_text": str(norm_res["value"]) if norm_res["value"] is not None else (it.value_text or "-"),
                "status": it.status if it else "NORMAL",
                "is_converted": norm_res["is_converted"],
                "raw_value": norm_res["raw_value"],
                "raw_unit": norm_res["raw_unit"]
            }

        # 临床优先级排序：1. 肿瘤标志物 2. 异常指标 3. 毒副器官指标 4. 慢病指标 5. 其他
        def sort_priority(item_info):
            cat = item_info["category"]
            if cat == "tumor_marker":
                return 10
            if item_info["has_abnormal"]:
                return 20
            if cat == "safety_toxicity":
                return 30
            if cat == "chronic":
                return 40
            return 50

        sorted_indicators = sorted(indicator_groups.values(), key=sort_priority)

        indicator_comparison = []
        for info in sorted_indicators:
            date_map = info["date_map"]
            values = []
            for d in recent_dates:
                entry = date_map.get(d)
                values.append({
                    "date": d,
                    "val": entry["val"] if entry else None,
                    "val_text": entry["val_text"] if entry else "-",
                    "status": entry["status"] if entry else "NORMAL",
                    "is_converted": entry.get("is_converted", False) if entry else False,
                    "raw_value": entry.get("raw_value") if entry else None,
                    "raw_unit": entry.get("raw_unit") if entry else ""
                })
            indicator_comparison.append({
                "code": info["code"],
                "name": info["name"],
                "category": info["category"],
                "unit": info["unit"],
                "ref_range": info["ref_range"],
                "values": values
            })

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
            "recent_lab_reports": [
                {
                    "id": r.id,
                    "type": r.report_type,
                    "date": r.report_date,
                    "hospital": r.hospital,
                    "summary": r.ai_summary
                } for r in lab_reports_db
            ],
            "lab_trend_comparison": {
                "dates": recent_dates,
                "indicators": indicator_comparison
            }
        }
        return report

report_generator = ReportGeneratorService()
