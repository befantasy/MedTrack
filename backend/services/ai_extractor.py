import base64
import json
import re
from typing import Dict, Any, Optional, Tuple
import httpx
from config import settings

def build_chat_endpoint(base_url: str) -> str:
    """智能清洗并构建 OpenAI 兼容的 /chat/completions 完整请求端点"""
    url = (base_url or "").strip().rstrip('/')
    if not url:
        return "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

    # 1. 用户已经填写了完整路径
    if url.endswith("/chat/completions"):
        return url

    # 2. 官方 Google Gemini OpenAI-compatible 接口
    if "generativelanguage.googleapis.com" in url:
        if url.endswith("/openai"):
            return f"{url}/chat/completions"
        elif url.endswith("/v1beta"):
            return f"{url}/openai/chat/completions"
        elif not ("/openai" in url):
            return f"{url}/v1beta/openai/chat/completions"
        return f"{url}/chat/completions"

    # 3. 常见以 /v1, /v1beta, /api/v1 结尾的地址 (sub2api, OneAPI, NewAPI, OpenAI)
    if url.endswith("/v1") or url.endswith("/v1beta") or url.endswith("/api/v1"):
        return f"{url}/chat/completions"

    # 4. 如果 URL 中已经包含 /v1/ 或 /v1beta/ (例如某些特定网关路径)
    if "/v1/" in url or "/v1beta/" in url:
        return f"{url}/chat/completions"

    # 5. 用户仅填写了中转站根域名 (如 https://api.medai.link 或 https://api.openai.com)
    # 自动容错补全 /v1/chat/completions
    return f"{url}/v1/chat/completions"

class AIExtractorService:
    """多模态视觉大模型智能医疗单据结构化解析器"""

    def __init__(self):
        self.default_api_key = settings.AI_API_KEY
        self.default_base_url = settings.AI_BASE_URL.rstrip('/')
        self.default_model = settings.AI_MODEL

    def get_config(self, db: Optional[Any] = None) -> Tuple[str, str, str]:
        """动态获取当前生效的 API Key, Base URL, Model，优先数据库配置，次选环境变量"""
        api_key = ""
        base_url = ""
        model = ""
        if db is not None:
            try:
                import models
                setting_rows = db.query(models.SystemSetting).filter(
                    models.SystemSetting.key.in_(["ai_api_key", "ai_base_url", "ai_model"])
                ).all()
                settings_map = {row.key: row.value for row in setting_rows}
                api_key = settings_map.get("ai_api_key", "").strip()
                base_url = settings_map.get("ai_base_url", "").strip()
                model = settings_map.get("ai_model", "").strip()
            except Exception:
                pass

        api_key = api_key or self.default_api_key
        base_url = base_url or self.default_base_url
        model = model or self.default_model
        return api_key, base_url.rstrip('/'), model

    async def test_connection(self, api_key: str, base_url: str, model: str) -> Dict[str, Any]:
        """轻量级连通性测试"""
        import time
        endpoint = build_chat_endpoint(base_url)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 10
        }
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(endpoint, json=payload, headers=headers)
                latency = int((time.time() - start_time) * 1000)
                if res.status_code == 200:
                    return {
                        "success": True,
                        "endpoint": endpoint,
                        "latency_ms": latency,
                        "message": f"连通成功！模型 [{model}] 响应正常 (耗时 {latency}ms)"
                    }
                else:
                    detail = res.text[:300]
                    hint = ""
                    if res.status_code == 404:
                        hint = " (404 错误通常是路径缺少 /v1，系统现已自动兼容补全，请核对中转站域名是否正确)"
                    elif res.status_code == 401:
                        hint = " (401 错误表示 API Key 密钥错误或中转站令牌无权限)"
                    elif res.status_code == 400:
                        hint = f" (400 错误通常是模型名称 [{model}] 在中转站不存在或不支持)"
                    return {
                        "success": False,
                        "endpoint": endpoint,
                        "status_code": res.status_code,
                        "message": f"HTTP {res.status_code}{hint}: {detail}"
                    }
        except Exception as e:
            return {
                "success": False,
                "endpoint": endpoint,
                "message": f"网络连接异常: {str(e)}"
            }

    async def analyze_document(self, file_bytes: bytes, mime_type: str, doc_type: str, db: Optional[Any] = None) -> Dict[str, Any]:
        """
        统一入口:
        doc_type: 'lab' (化验单), 'imaging' (影像报告), 'pathology' (病理单), 'discharge' (出院记录/化疗单)
        """
        api_key, base_url, model = self.get_config(db)

        # 如果未配置 API Key，直接抛出异常
        if not api_key or api_key == "your_api_key_here":
            raise ValueError("未配置大模型 API Key，请在【系统管理】或环境变量中配置。")

        prompt = self._get_prompt_for_type(doc_type)
        b64_image = base64.b64encode(file_bytes).decode('utf-8')
        
        # 兼容处理图片 MIME
        if not mime_type or mime_type == "application/octet-stream":
            mime_type = "image/jpeg"

        messages = [
            {
                "role": "system",
                "content": "你是一个资深的肿瘤与慢性病临床医学专家助手。请仔细阅读用户提供的医疗单据图像或文本，严格以纯 JSON 格式输出结构化提取结果，禁止包含任何 Markdown 代码块外的闲聊文字。"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64_image}"
                        }
                    }
                ]
            }
        ]

        endpoint = build_chat_endpoint(base_url)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                
                # 兼容性容错：若中转站因 response_format 返回 400 不支持，自动移除后重试
                if response.status_code == 400 and ("response_format" in response.text or "format" in response.text):
                    payload.pop("response_format", None)
                    response = await client.post(endpoint, json=payload, headers=headers)

                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = self._clean_and_parse_json(content)
                parsed["_is_mock"] = False
                parsed["_model_used"] = model
                return parsed
        except Exception as e:
            # 抛出真实异常，由上传路由捕获并记录，不再返回占位数据
            raise RuntimeError(f"大模型解析失败 [{endpoint}]: {str(e)}")

    def _clean_and_parse_json(self, text: str) -> Dict[str, Any]:
        """清除 markdown 标签并提取合法 JSON"""
        text = text.strip()
        # 1. 优先提取 ```json ... ``` 中的内容
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
        else:
            # 2. 提取首个 { 到最后一个 }
            bracket_match = re.search(r"(\{[\s\S]*\})", text)
            if bracket_match:
                text = bracket_match.group(1).strip()
        return json.loads(text)

    def _get_prompt_for_type(self, doc_type: str) -> str:
        if doc_type == "lab":
            return """
你是一名资深肿瘤科与临床检验医学专家。请精准识别分析检验化验单，重点提取血常规五分类、生化肝肾功能、电解质、血糖、凝血以及肿瘤标志物全套（包括但不限于 CEA, CA199, CA125, CA153, AFP, CYFRA21-1, NSE, SCC, PSA, CA72-4, 铁蛋白等）。

【重要核心要求】：
1. 提炼的 ai_summary 必须严谨、专业，按顺序包含以下三部分（客观总结陈述 + 关注提示 + 建议）：
   - ①【客观总结陈述】：对化验单整体情况进行客观综合评价（例如：“本次检验涵盖生化全套与血糖血脂指标，总体评估代谢与脂质水平存在偏高，肾功能与电解质保持正常。”；若全部指标均在正常范围，则直接写为：“各项检验指标均在正常参考范围内，未见异常波动。”）。
   - ②【关注提示】：若存在任何“偏高(↑)”、“偏低(↓)”或“异常/阳性”指标，必须以“关注: ”或“异常指标: ”明确开头，逐一列出：指标中文全称及英文代码、具体实测测定值、计量单位、参考区间以及偏高/偏低判定。例如：“关注: 葡萄糖(GLU) 9.14 mmol/L (↑偏高, 参考:3.89-6.11)、总胆固醇(CHOL) 7.06 mmol/L (↑偏高, 参考:0-5.17)、低密度脂蛋白胆固醇(LDL-C) 5.54 mmol/L (↑偏高, 参考:0-3.4)；其余指标均在正常参考范围内。”。必须包含具体的测定数值与参考区间，严禁仅使用泛泛概括！若全项指标均正常，则可省略此项或注明“未见异常指标”。
   - ③【建议】：必须以“建议: ”明确开头，结合上述关注指标与临床实际，给出科学实用的医学复查、就医随访或生活方式干预建议（例如：“建议: 定期监测空腹血糖与血脂谱，低糖低脂清淡饮食，必要时门诊复查评估。”）。
2. items 数组中必须对化验单的每一项进行准确结构化提取：
   - 精准识别化验单原件上的异常提示标记（如 ↑、↓、H、L、+、阳性、弱阳性等）。
   - status 字段必须严格判定：正常为 "NORMAL"，偏高为 "HIGH"，偏低为 "LOW"，定性阳性/可疑为 "ABNORMAL"。
   - 提取纯数值 value（浮点数）与原始文本 value_text、单位 unit、参考下限 ref_min、参考上限 ref_max、参考区间文本 ref_range。

请严格按以下 JSON 结构输出，不要包含任何 markdown 之外的解释：
{
  "report_type": "化验单类型 (如: 肿瘤标志物全套 / 血常规五分类 / 肝肾功能综合)",
  "report_date": "检验日期 (YYYY-MM-DD)",
  "hospital": "医院名称",
  "ai_summary": "客观总结陈述。 关注: 指标名(代码) 数值 单位 (↑偏高/↓偏低, 参考:区间)；其余指标均在正常参考范围内。 建议: 具体随访与就医建议。",
  "items": [
    {
      "item_name": "指标中文全称 (如: 癌胚抗原)",
      "item_code": "通用英文字母缩写 (如: CEA, WBC, PLT, GLU, ALT, AST, Cr, UA, CA125, CA199)",
      "category": "类别 (可选: tumor_marker, safety_toxicity, chronic, other)",
      "value": 5.8,
      "value_text": "5.8",
      "unit": "ng/mL",
      "ref_min": 0.0,
      "ref_max": 5.0,
      "ref_range": "0-5.0",
      "status": "HIGH"
    }
  ]
}
"""
        elif doc_type == "imaging":
            return """
你是一名资深放射影像科专家。请精准识别分析医学影像报告（CT / 增强CT / MRI / PET-CT / 超声 / 骨扫描 / X线）：

【重要核心要求】：
1. 详细客观归纳 findings（检查所见）：包含原发病灶位置、最大长短径尺寸（mm/cm）、形态密度/信号强化特征、各引流区淋巴结大小、胸腹水、远处脏器（肝、肺、骨、脑等）是否有可疑转移结节。
2. 完整提炼 impression（影像诊断结论），必须包含【客观总结陈述】+【异常病灶提示】+【建议】：
   - 客观总结陈述：检查方式、部位与整体表现概述。
   - 异常病灶提示：明确列出所有阳性/可疑异常病变及测量尺寸（如“异常病灶: 右肺下叶背段结节14mm x 11mm，纵隔4R淋巴结肿大12mm；其余肺野未见新发病灶。”），并注明 RECIST 评估倾向（PR / SD / PD / CR）。
   - 建议：以“建议: ”明确开头，给出随访复查周期或多学科会诊建议（如“建议: 2-3个月后复查胸腹部增强CT对比观察。”）。
3. target_lesions 数组提取所有测量了具体尺寸的靶病灶部位、具体尺寸与变化。

请严格按以下 JSON 结构输出：
{
  "modality": "检查类别 (如: 胸部平扫加增强CT / 颅脑增强MRI / 全身PET-CT)",
  "body_part": "检查部位 (如: 胸部 / 腹盆部 / 颅脑)",
  "report_date": "报告日期 (YYYY-MM-DD)",
  "hospital": "医院名称",
  "target_lesions": [
    {
      "site": "靶病灶部位 (如: 右肺下叶背段结节)",
      "size": "当前病灶具体尺寸 (如: 14mm x 11mm)",
      "status": "病灶变化 (如: 较前片缩小 / 新发病灶 / 保持稳定)"
    }
  ],
  "recist_evaluation": "RECIST疗效评估 (PR部分缓解 / SD疾病稳定 / PD疾病进展 / CR完全缓解 / 未明确对比)",
  "findings": "检查所见详细客观记录（包含原发灶、转移灶、各器官结节具体尺寸数据）",
  "impression": "客观总结陈述。 异常病灶: 重点列出病灶位置与具体尺寸。 建议: 规范随访复查建议。"
}
"""
        elif doc_type == "pathology":
            return """
你是一名资深肿瘤病理学与分子遗传学专家。请精准分析病理诊断报告与分子基因检测报告单：

【重要核心要求】：
1. histological_diagnosis（病理诊断结论）：必须包含【客观总结陈述】+【病理/突变异常提示】+【建议】：
   - 客观总结陈述：取材部位、组织学明确诊断与分化程度。
   - 异常提示：浸润深度、脉管癌栓/神经侵犯、切缘性质、淋巴结转移枚数（如: 2/18）、免疫组化特征标志（如 Ki-67、PD-L1）及驱动基因敏感突变（如 EGFR 19-del 丰度32.4%）。
   - 建议：以“建议: ”明确开头，提示后续多学科综合诊治或靶向用药评估建议。
2. ihc_markers（免疫组化）：详细列出所有免疫组化指标的阴阳性或量化表达结果（如 ER、PR、HER2(0/1+/2+/3+)、Ki-67增殖指数(如: 30%)、PD-L1 TPS/CPS、CK7、TTF-1、Napsin A等）。
3. genetic_testing（基因/靶向突变）：提取具体突变位点或融合状态（如 EGFR 19-del缺失突变、EGFR L858R、ALK融合、KRAS G12D、ROS1、MET 14跳跃突变、BRAF V600E等，注明突变丰度或阴/阳性判定）。

请严格按以下 JSON 结构输出：
{
  "sample_type": "标本类型 (手术切除标本 / 经皮穿刺活检 / 支气管镜活检 / 胸水细胞学)",
  "sample_site": "取材部位 (如: 右肺中叶占位 / 纵隔淋巴结)",
  "report_date": "病理报告日期 (YYYY-MM-DD)",
  "hospital": "医院名称",
  "histological_diagnosis": "客观总结陈述。 异常提示: ... 建议: ...",
  "differentiation": "分化程度 (高分化 / 中分化 / 低分化 / 未分化)",
  "ihc_markers": {
    "CK7": "阳性(+)",
    "TTF-1": "阳性(+)",
    "Napsin A": "阳性(+)",
    "Ki-67": "热区30%阳性",
    "P40": "阴性(-)"
  },
  "genetic_testing": {
    "EGFR": "第19号外显子缺失突变 (19-del, 丰度32.4%)",
    "ALK": "阴性 (D5F3)",
    "KRAS": "野生型",
    "PD-L1": "TPS=60% (强阳性)"
  }
}
"""
        else: # discharge or chemotherapy cycle
            return """
请分析出院小结、门诊化疗单或治疗记录单，提取手术与抗肿瘤治疗周期信息：
{
  "doc_type": "discharge_or_therapy",
  "hospital": "医院名称",
  "record_date": "记录日期 (YYYY-MM-DD)",
  "surgery_info": {
    "surgery_name": "手术术式 (无手术写空)",
    "surgery_date": "手术日期 (YYYY-MM-DD)",
    "margins": "切缘 (R0/R1)",
    "lymph_nodes": "淋巴结转移清扫情况 (如: 1/15)"
  },
  "therapy_info": {
    "treatment_line": "阶段/线数 (新辅助 / 术后辅助 / 一线治疗 / 维持治疗)",
    "therapy_type": "疗法 (化疗 / 靶向治疗 / 免疫治疗 / 联合方案)",
    "regimen_name": "方案名称 (如: 培美曲塞 + 卡铂, 奥希替尼)",
    "cycle_number": 1,
    "drugs_detail": "用药剂量明细",
    "adverse_events": "记录的毒副反应 (如: 骨髓抑制II度, 轻度恶心)"
  }
}
"""

    def _get_mock_data(self, doc_type: str) -> Dict[str, Any]:
        """当未配置真实大模型 API 密钥时提供的医学级标准演示数据"""
        if doc_type == "lab":
            return {
                "report_type": "肿瘤标志物与血常规生化综合检验",
                "report_date": "2026-03-10",
                "hospital": "肿瘤中心检验科",
                "ai_summary": "【异常指标】癌胚抗原(CEA) 6.8 ng/mL (↑轻度偏高, 参考:0-5.0)；糖类抗原19-9(CA199) 42.5 U/mL (↑偏高, 参考:0-37.0)；空腹血糖(GLU) 6.4 mmol/L (↑偏高, 参考:3.9-6.1)。其余血常规五分类与肝肾功能指标均在正常参考范围内。",
                "items": [
                    {"item_name": "癌胚抗原", "item_code": "CEA", "category": "tumor_marker", "value": 6.8, "value_text": "6.8", "unit": "ng/mL", "ref_min": 0.0, "ref_max": 5.0, "ref_range": "0-5.0", "status": "HIGH"},
                    {"item_name": "糖类抗原19-9", "item_code": "CA199", "category": "tumor_marker", "value": 42.5, "value_text": "42.5", "unit": "U/mL", "ref_min": 0.0, "ref_max": 37.0, "ref_range": "0-37.0", "status": "HIGH"},
                    {"item_name": "白细胞计数", "item_code": "WBC", "category": "safety_toxicity", "value": 5.4, "value_text": "5.4", "unit": "10^9/L", "ref_min": 3.5, "ref_max": 9.5, "ref_range": "3.5-9.5", "status": "NORMAL"},
                    {"item_name": "中性粒细胞绝对值", "item_code": "NEUT#", "category": "safety_toxicity", "value": 3.2, "value_text": "3.2", "unit": "10^9/L", "ref_min": 1.8, "ref_max": 6.3, "ref_range": "1.8-6.3", "status": "NORMAL"},
                    {"item_name": "血小板计数", "item_code": "PLT", "category": "safety_toxicity", "value": 185.0, "value_text": "185", "unit": "10^9/L", "ref_min": 125.0, "ref_max": 350.0, "ref_range": "125-350", "status": "NORMAL"},
                    {"item_name": "空腹血糖", "item_code": "GLU", "category": "chronic", "value": 6.4, "value_text": "6.4", "unit": "mmol/L", "ref_min": 3.9, "ref_max": 6.1, "ref_range": "3.9-6.1", "status": "HIGH"},
                    {"item_name": "血肌酐", "item_code": "Cr", "category": "safety_toxicity", "value": 78.0, "value_text": "78", "unit": "μmol/L", "ref_min": 44.0, "ref_max": 97.0, "ref_range": "44-97", "status": "NORMAL"},
                    {"item_name": "谷丙转氨酶", "item_code": "ALT", "category": "safety_toxicity", "value": 24.0, "value_text": "24", "unit": "U/L", "ref_min": 7.0, "ref_max": 40.0, "ref_range": "7-40", "status": "NORMAL"}
                ]
            }
        elif doc_type == "imaging":
            return {
                "modality": "胸腹部增强CT扫描",
                "body_part": "胸部及全腹部",
                "report_date": "2026-03-08",
                "hospital": "医学影像诊断中心",
                "target_lesions": [
                    {"site": "右肺下叶背段", "size": "13mm x 10mm", "status": "较2025-12月片(18mm x 14mm)明显缩小"}
                ],
                "recist_evaluation": "PR部分缓解",
                "findings": "右肺下叶背段结节，边缘略分叶，内部密度欠均，现病灶大小约 13mm x 10mm，较前次复查显著退缩。纵隔及肺门无明显肿大淋巴结。肝脾胰肾未见异常强化灶。",
                "impression": "右肺下叶占位性病变抗肿瘤治疗后复查：病灶较前缩小，疗效评价考虑为部分缓解 (PR)；腹腔脏器未见转移征象。"
            }
        elif doc_type == "pathology":
            return {
                "sample_type": "支气管镜穿刺活检标本",
                "sample_site": "右肺下叶占位",
                "report_date": "2025-10-15",
                "hospital": "病理科中心实验室",
                "histological_diagnosis": "(右肺下叶穿刺) 结合免疫组化形态，符合浸润性肺腺癌，中-低分化。",
                "differentiation": "中-低分化",
                "ihc_markers": {
                    "CK7": "阳性(+)",
                    "TTF-1": "强阳性(++)",
                    "Napsin A": "阳性(+)",
                    "P40": "阴性(-)",
                    "Ki-67": "热点区约35%阳性"
                },
                "genetic_testing": {
                    "EGFR": "Exon 19 缺失突变 (p.E746_A750del 阳性)",
                    "ALK": "Ventana D5F3 阴性",
                    "ROS1": "阴性",
                    "KRAS": "野生型",
                    "PD-L1": "22C3 mAb 检测 TPS ≈ 50%"
                }
            }
        else:
            return {
                "doc_type": "discharge_or_therapy",
                "hospital": "胸部肿瘤内科",
                "record_date": "2026-02-20",
                "surgery_info": {
                    "surgery_name": "胸腔镜右肺下叶切除术+纵隔淋巴结清扫",
                    "surgery_date": "2025-11-05",
                    "margins": "R0",
                    "lymph_nodes": "1/16"
                },
                "therapy_info": {
                    "treatment_line": "术后辅助靶向治疗",
                    "therapy_type": "靶向治疗",
                    "regimen_name": "甲磺酸奥希替尼片 (泰瑞沙)",
                    "cycle_number": 3,
                    "drugs_detail": "奥希替尼 80mg 口服 每日一次",
                    "adverse_events": "轻度甲沟炎(I度)，偶发皮疹，无腹泻"
                }
            }

ai_extractor = AIExtractorService()
