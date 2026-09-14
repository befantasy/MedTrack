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

        # 如果未配置 API Key，返回高质量模拟测试数据，并显式标注 _is_mock
        if not api_key or api_key == "your_api_key_here":
            mock = self._get_mock_data(doc_type)
            mock["_is_mock"] = True
            mock["_mock_notice"] = "未配置大模型 API Key（AI_API_KEY），当前展示内置演示样例数据。请在【系统管理】或 VPS 环境变量中配置 API Key 以启用真实 AI 识别。"
            return mock

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
                
                # 兼容性容错：若中转站对 response_format 返回 400 不支持，自动移除后重试
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
            # 大模型调用出错时的保护：附带真实错误信息并降级返回模拟数据，保证页面不崩
            mock = self._get_mock_data(doc_type)
            mock["_is_mock"] = True
            mock["_error"] = f"大模型请求异常 [{endpoint}]: {str(e)}"
            mock["_mock_notice"] = f"大模型解析失败 ({str(e)})，已自动回退到模拟数据。"
            return mock

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
请识别分析化验单/检验报告单，重点提取血常规、生化肝肾功、电解质、血糖以及肿瘤标志物（如CEA, CA199, CA125, CA153, AFP, CYFRA21-1, NSE, PSA等）。
请严格按以下 JSON 结构输出：
{
  "report_type": "化验单类型 (如: 肿瘤标志物全套 / 血常规五分类 / 肝肾功能)",
  "report_date": "检验日期 (YYYY-MM-DD)",
  "hospital": "医院名称",
  "ai_summary": "一两句话总结本次化验的核心异常指标",
  "items": [
    {
      "item_name": "指标中文全称 (如: 癌胚抗原)",
      "item_code": "通用英文字母缩写 (如: CEA, WBC, PLT, GLU, ALT, AST, Cr, UA)",
      "category": "类别 (可选: tumor_marker, safety_toxicity, chronic, other)",
      "value": 5.8, // 纯浮点数数值，无法解析为数字的设为 null
      "value_text": "5.8", // 原始字符
      "unit": "ng/mL", // 单位
      "ref_min": 0.0, // 参考下限数值
      "ref_max": 5.0, // 参考上限数值
      "ref_range": "0-5.0", // 参考区间原文
      "status": "HIGH" // 可选: NORMAL(正常), HIGH(偏高), LOW(偏低), ABNORMAL(异常)
    }
  ]
}
"""
        elif doc_type == "imaging":
            return """
请分析医学影像报告（CT / 增强CT / MRI / PET-CT / 超声 / 骨扫描）：
请严格按以下 JSON 结构输出：
{
  "modality": "检查类别 (如: 胸部平扫加增强CT / 颅脑增强MRI / 全身PET-CT)",
  "body_part": "检查部位 (如: 胸部 / 腹盆部 / 颅脑)",
  "report_date": "报告日期 (YYYY-MM-DD)",
  "hospital": "医院名称",
  "target_lesions": [
    {
      "site": "靶病灶部位 (如: 右肺下叶背段)",
      "size": "当前病灶尺寸 (如: 14mm x 11mm)",
      "status": "变化描述 (如: 较前片略有缩小)"
    }
  ],
  "recist_evaluation": "RECIST疗效初步评估 (可选: PR部分缓解 / SD疾病稳定 / PD疾病进展 / CR完全缓解 / 未明确对比)",
  "findings": "检查所见详细归纳",
  "impression": "影像学诊断结论完整摘录"
}
"""
        elif doc_type == "pathology":
            return """
请分析病理诊断报告与分子基因检测报告单：
请严格按以下 JSON 结构输出：
{
  "sample_type": "标本类型 (手术切除 / 穿刺活检 / 支气管镜活检 / 细胞学)",
  "sample_site": "取材部位 (如: 右肺中叶占位 / 纵隔淋巴结)",
  "report_date": "病理报告日期 (YYYY-MM-DD)",
  "hospital": "医院名称",
  "histological_diagnosis": "病理学明确诊断 (如: (右肺下叶)浸润性腺癌，腺泡型为主伴乳头状结构)",
  "differentiation": "分化程度 (高分化 / 中分化 / 低分化)",
  "ihc_markers": {
    "CK7": "阳性(+)",
    "TTF-1": "阳性(+)",
    "Napsin A": "阳性(+)",
    "P40": "阴性(-)"
  },
  "genetic_testing": {
    "EGFR": "第19号外显子缺失突变 (19-del)",
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
                "ai_summary": "癌胚抗原(CEA)与CA19-9轻度偏高，白细胞与血小板正常，肝肾功能指标良好。",
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
