import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from auth import get_current_user
from config import settings
from services.ai_extractor import ai_extractor

router = APIRouter(prefix="/upload", tags=["文件上传与AI解析"])

@router.post("/parse-doc")
async def upload_and_parse_document(
    file: UploadFile = File(...),
    doc_type: str = Form("lab"), # lab, imaging, pathology, discharge
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    上传单据图片/PDF，触发多模态大模型进行结构化抽取并返回预览结果
    """
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".bmp"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="不支持的文件格式，请上传 JPG, PNG, WEBP 或 PDF 格式文件")

    # 保持唯一文件名并落盘
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    file_bytes = await file.read()
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    raw_file_url = f"/uploads/{unique_filename}"

    # 调用 AI 视觉抽取引擎
    mime_type = file.content_type or "image/jpeg"
    extracted_data = await ai_extractor.analyze_document(file_bytes, mime_type, doc_type)

    return {
        "success": True,
        "filename": file.filename,
        "raw_file_url": raw_file_url,
        "doc_type": doc_type,
        "parsed_data": extracted_data
    }
