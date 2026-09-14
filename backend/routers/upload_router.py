import os
import uuid
import asyncio
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
import models
from auth import get_current_user
from config import settings
from services.ai_extractor import ai_extractor

router = APIRouter(prefix="/upload", tags=["文件上传与AI解析"])

batch_tasks: Dict[str, Dict[str, Any]] = {}

async def process_batch_task(task_id: str, files_info: List[dict], doc_type: str):
    db = SessionLocal()
    try:
        for idx, f_info in enumerate(files_info):
            file_path = f_info["file_path"]
            mime_type = f_info["mime_type"]
            filename = f_info["filename"]
            raw_url = f_info["raw_file_url"]

            try:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()

                extracted_data = await ai_extractor.analyze_document(file_bytes, mime_type, doc_type, db=db)
                
                batch_tasks[task_id]["results"].append({
                    "success": True,
                    "filename": filename,
                    "raw_file_url": raw_url,
                    "doc_type": doc_type,
                    "parsed_data": extracted_data,
                    "original_index": idx
                })
            except Exception as e:
                batch_tasks[task_id]["errors"].append(f"文件 {filename} 解析失败: {str(e)}")
            
            batch_tasks[task_id]["completed"] += 1
            
            # 延时2秒，防止请求过密击穿中转站的 Token Lock
            if idx < len(files_info) - 1:
                await asyncio.sleep(2.0)
                
        batch_tasks[task_id]["status"] = "completed"
    except Exception as e:
        batch_tasks[task_id]["status"] = "error"
        batch_tasks[task_id]["errors"].append(f"批量任务严重异常: {str(e)}")
    finally:
        db.close()

@router.post("/parse-batch")
async def upload_and_parse_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    doc_type: str = Form("lab"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".bmp"}
    
    files_info = []
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_extensions:
            continue
        
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        
        file_bytes = await file.read()
        with open(file_path, "wb") as f:
            f.write(file_bytes)
            
        files_info.append({
            "filename": file.filename,
            "file_path": file_path,
            "raw_file_url": f"/uploads/{unique_filename}",
            "mime_type": file.content_type or "image/jpeg"
        })
        
    if not files_info:
        raise HTTPException(status_code=400, detail="没有有效的图片或PDF文件")

    task_id = str(uuid.uuid4())
    batch_tasks[task_id] = {
        "total": len(files_info),
        "completed": 0,
        "status": "processing",
        "results": [],
        "errors": []
    }
    
    background_tasks.add_task(process_batch_task, task_id, files_info, doc_type)
    
    return {"success": True, "task_id": task_id}

@router.get("/parse-batch/{task_id}")
async def get_batch_status(
    task_id: str,
    current_user: models.User = Depends(get_current_user)
):
    if task_id not in batch_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
        
    task = batch_tasks[task_id]
    
    if task["status"] == "completed":
        task["results"] = sorted(task["results"], key=lambda x: x["original_index"])
        
    return task

@router.post("/parse-doc")
async def upload_and_parse_document(
    file: UploadFile = File(...),
    doc_type: str = Form("lab"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".bmp"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="不支持的文件格式，请上传 JPG, PNG, WEBP 或 PDF 格式文件")

    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    file_bytes = await file.read()
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    raw_file_url = f"/uploads/{unique_filename}"
    mime_type = file.content_type or "image/jpeg"
    extracted_data = await ai_extractor.analyze_document(file_bytes, mime_type, doc_type, db=db)

    return {
        "success": True,
        "filename": file.filename,
        "raw_file_url": raw_file_url,
        "doc_type": doc_type,
        "parsed_data": extracted_data
    }
