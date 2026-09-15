"""
MedTrack 临床检验指标单位智能归一化与换算服务
针对不同医院检验科仪器、试剂盒差异导致的单位不统一问题，
在呈现趋势图表和多期报告对比时，自动将数值与参考区间换算至国家临床标准基准单位，
消除坐标轴上因单位不同引发的虚假数倍/千倍“断崖式剧烈波动”。
"""

import re
from typing import Optional, Dict, Any

# 标准临床基准单位定义 (国家卫健委/临床检验中心推荐基准单位)
STANDARD_UNITS: Dict[str, str] = {
    # 肿瘤标志物
    "CEA": "ng/mL",
    "AFP": "ng/mL",
    "CYFRA21-1": "ng/mL",
    "NSE": "ng/mL",
    "PSA": "ng/mL",
    "FPSA": "ng/mL",
    "SCC": "ng/mL",
    "FER": "ng/mL",
    "CA199": "U/mL",
    "CA125": "U/mL",
    "CA153": "U/mL",
    "CA724": "U/mL",
    "CA50": "U/mL",
    "CA242": "U/mL",
    # 血常规
    "WBC": "10^9/L",
    "PLT": "10^9/L",
    "NEUT#": "10^9/L",
    "LYMPH#": "10^9/L",
    "MONO#": "10^9/L",
    "EOS#": "10^9/L",
    "BASO#": "10^9/L",
    "RBC": "10^12/L",
    "HGB": "g/L",
    # 肝功能与酶学
    "ALT": "U/L",
    "AST": "U/L",
    "GGT": "U/L",
    "ALP": "U/L",
    "LDH": "U/L",
    "CK": "U/L",
    "AMY": "U/L",
    "TBIL": "umol/L",
    "DBIL": "umol/L",
    "IBIL": "umol/L",
    "ALB": "g/L",
    "TP": "g/L",
    "GLO": "g/L",
    # 肾功能与代谢
    "CR": "umol/L",
    "UA": "umol/L",
    "BUN": "mmol/L",
    "GLU": "mmol/L",
    "TC": "mmol/L",
    "TG": "mmol/L",
    "HDL-C": "mmol/L",
    "LDL-C": "mmol/L",
    # 电解质
    "K": "mmol/L",
    "NA": "mmol/L",
    "CL": "mmol/L",
    "CA": "mmol/L",
    "P": "mmol/L",
    "MG": "mmol/L",
    # 凝血
    "FIB": "g/L",
    "D-DIMER": "mg/L"
}


def clean_unit_str(raw_unit: Optional[str]) -> str:
    """清理并标准化单位文本字符串，移除多余空格、统一微米符号等"""
    if not raw_unit:
        return ""
    u = str(raw_unit).strip()
    # 统一希腊字母 μ 与英文 u
    u = u.replace("μ", "u").replace("Μ", "u").replace("µ", "u")
    # 统一中文字符和星号乘号
    u = u.replace("×", "*").replace("X", "*").replace("x", "*")
    u = re.sub(r"\s+", "", u)
    return u


def normalize_lab_unit_and_value(
    item_code: str,
    value: Optional[float],
    unit: Optional[str],
    ref_min: Optional[float] = None,
    ref_max: Optional[float] = None,
    ref_range: Optional[str] = ""
) -> Dict[str, Any]:
    """
    根据指标代码及其原始单位，智能检测并换算至临床标准单位。
    返回字典结构：
    {
        "value": float or None,               # 换算后的标准值
        "unit": str,                          # 标准基准单位
        "ref_min": float or None,             # 换算后的参考下限
        "ref_max": float or None,             # 换算后的参考上限
        "ref_range": str,                     # 换算后格式化的参考区间
        "is_converted": bool,                 # 是否发生了数值换算
        "raw_value": float or None,           # 原始测量值
        "raw_unit": str                       # 原始单位文本
    }
    """
    raw_val = value
    raw_u = unit or ""
    clean_u = clean_unit_str(raw_u).lower()
    code_upper = (item_code or "").upper().strip()

    # 规范化别名
    if code_upper in ("CA19-9", "CA-199"):
        code_upper = "CA199"
    elif code_upper in ("CA-125",):
        code_upper = "CA125"
    elif code_upper in ("CA-153", "CA15-3"):
        code_upper = "CA153"
    elif code_upper in ("CREA", "CRE", "肌酐", "血肌酐"):
        code_upper = "CR"
    elif code_upper in ("HB", "HGB", "血红蛋白"):
        code_upper = "HGB"
    elif code_upper in ("GLUCOSE", "血糖", "空腹血糖"):
        code_upper = "GLU"
    elif code_upper in ("URIC", "尿酸"):
        code_upper = "UA"

    std_unit = STANDARD_UNITS.get(code_upper, raw_u)
    
    # 若无数值或无单位定义，原样返回
    if value is None:
        return {
            "value": None,
            "unit": std_unit or raw_u,
            "ref_min": ref_min,
            "ref_max": ref_max,
            "ref_range": ref_range or "",
            "is_converted": False,
            "raw_value": None,
            "raw_unit": raw_u
        }

    factor = 1.0
    is_converted = False

    # ---------------- 1. 肿瘤标志物 (标准: ng/mL 或 U/mL) ----------------
    if std_unit == "ng/mL":
        if clean_u in ("pg/ml", "ng/l"):
            factor = 0.001
            is_converted = True
        elif clean_u in ("mg/l",):
            factor = 1000.0
            is_converted = True
        elif clean_u in ("ug/l", "ng/ml"):
            factor = 1.0
            is_converted = (clean_u == "ug/l")

    elif std_unit == "U/mL":
        if clean_u in ("u/l", "iu/l", "mu/ml"):
            factor = 0.001
            is_converted = True
        elif clean_u in ("u/ml", "ku/l", "iu/ml"):
            factor = 1.0

    # ---------------- 2. 血常规细胞计数 (标准: 10^9/L 或 10^12/L) ----------------
    elif std_unit == "10^9/L":
        # 如果写法是 /ul, /mm3, 且数值较大 (大于 50)，说明是绝对个数未除以 10^9
        if clean_u in ("/ul", "/mm3", "/mm^3", "ul", "mm3", "个/ul"):
            if value > 50:
                factor = 0.001
                is_converted = True
        elif clean_u in ("10*4/ul", "10^4/ul", "10*4/ml"):
            factor = 10.0
            is_converted = True
        elif any(clean_u.startswith(p) for p in ("10^9", "10*9", "10e9", "*10^9", "g/l", "10^3/ul", "10*3/ul", "k/ul")):
            factor = 1.0

    elif std_unit == "10^12/L":
        if clean_u in ("/ul", "/mm3", "/mm^3", "ul", "mm3", "个/ul"):
            if value > 10000:
                factor = 0.000001
                is_converted = True
        elif clean_u in ("10^6/ul", "10*6/ul", "m/ul", "t/l"):
            factor = 1.0

    # ---------------- 3. 血红蛋白与总蛋白/白蛋白 (标准: g/L) ----------------
    elif std_unit == "g/L":
        if clean_u in ("g/dl", "g/100ml"):
            factor = 10.0
            is_converted = True
        elif clean_u in ("mg/dl", "mg/100ml"):
            factor = 0.01
            is_converted = True
        elif clean_u == "mmol/l" and code_upper == "HGB":
            factor = 16.11
            is_converted = True

    # ---------------- 4. 酶学活性 (标准: U/L) ----------------
    elif std_unit == "U/L":
        if clean_u in ("u/ml", "iu/ml"):
            factor = 1000.0
            is_converted = True

    # ---------------- 5. 肾功与代谢: 肌酐 (标准: umol/L) ----------------
    elif code_upper == "CR" and std_unit == "umol/L":
        if clean_u in ("mg/dl", "mg/100ml"):
            factor = 88.4
            is_converted = True
        elif clean_u in ("mmol/l",):
            factor = 1000.0
            is_converted = True

    # ---------------- 6. 尿酸 (标准: umol/L) ----------------
    elif code_upper == "UA" and std_unit == "umol/L":
        if clean_u in ("mg/dl", "mg/100ml"):
            factor = 59.48
            is_converted = True
        elif clean_u in ("mmol/l",):
            factor = 1000.0
            is_converted = True

    # ---------------- 7. 胆红素 (标准: umol/L) ----------------
    elif code_upper in ("TBIL", "DBIL", "IBIL") and std_unit == "umol/L":
        if clean_u in ("mg/dl", "mg/100ml"):
            factor = 17.1
            is_converted = True

    # ---------------- 8. 血糖 (标准: mmol/L) ----------------
    elif code_upper == "GLU" and std_unit == "mmol/L":
        if clean_u in ("mg/dl", "mg/100ml"):
            factor = 1.0 / 18.0182
            is_converted = True

    # ---------------- 9. 血脂与电解质 (标准: mmol/L) ----------------
    elif code_upper in ("TC", "HDL-C", "LDL-C") and std_unit == "mmol/L":
        if clean_u in ("mg/dl",):
            factor = 1.0 / 38.67
            is_converted = True
    elif code_upper == "TG" and std_unit == "mmol/L":
        if clean_u in ("mg/dl",):
            factor = 1.0 / 88.57
            is_converted = True
    elif code_upper == "CA" and std_unit == "mmol/L":
        if clean_u in ("mg/dl",):
            factor = 1.0 / 4.0
            is_converted = True

    # ---------------- 10. 凝血 FIB 与 D-二聚体 ----------------
    elif code_upper == "FIB" and std_unit == "g/L":
        if clean_u in ("mg/dl", "mg/100ml"):
            factor = 0.01
            is_converted = True
    elif code_upper == "D-DIMER" and std_unit == "mg/L":
        if clean_u in ("ug/l", "ng/ml"):
            factor = 0.001
            is_converted = True

    # 执行换算与精度四舍五入
    if is_converted and factor != 1.0:
        new_val = round(value * factor, 3 if abs(value * factor) < 10 else 2)
        new_ref_min = round(ref_min * factor, 2) if ref_min is not None else None
        new_ref_max = round(ref_max * factor, 2) if ref_max is not None else None
        
        # 联动更新区间文本
        new_range = ref_range
        if new_ref_min is not None and new_ref_max is not None:
            new_range = f"{new_ref_min}-{new_ref_max}"
        elif new_ref_max is not None:
            new_range = f"< {new_ref_max}"
    else:
        new_val = value
        new_ref_min = ref_min
        new_ref_max = ref_max
        new_range = ref_range

    return {
        "value": new_val,
        "unit": std_unit,
        "ref_min": new_ref_min,
        "ref_max": new_ref_max,
        "ref_range": new_range or "",
        "is_converted": is_converted,
        "raw_value": raw_val,
        "raw_unit": raw_u
    }
