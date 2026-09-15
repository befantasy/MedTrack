import os
import uuid
import asyncio
import io
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from PIL import Image

from database import get_db, SessionLocal
import models
from auth import get_current_user
from config import settings
from services.ai_extractor import ai_extractor

router = APIRouter(prefix="/upload", tags=["文件上传与AI解析"])

batch_tasks: Dict[str, Dict[str, Any]] = {}

def sanitize_segment(name: str, default: str = "general") -> str:
    """清理路径段，防止路径穿越及非法字符"""
    if not name:
        return default
    # 替换 Windows/Linux 非法字符: \ / : * ? " < > | 以及 URL 保留字符如 # % &
    cleaned = re.sub(r'[\\/:*?"<>|#%&]+', '_', str(name)).strip(". ")
    return cleaned if cleaned else default

def prepare_upload_target(username: str, doc_type: str, original_filename: str) -> Tuple[str, str, str]:
    """
    根据 用户名 / 文档类型 / 日期 / 文件名 构建目录结构及访问URL。
    处理重名情况：如果目标文件已存在，则自动添加递增数字后缀如 (1), (2)...
    返回: (target_file_path, raw_file_url, final_filename)
    """
    safe_user = sanitize_segment(username, default="unknown_user")
    safe_doc = sanitize_segment(doc_type, default="other")
    date_str = datetime.now().strftime("%Y-%m-%d")

    # 构建目标子目录: uploads/<username>/<doc_type>/<date>/
    target_dir = os.path.join(settings.UPLOAD_DIR, safe_user, safe_doc, date_str)
    os.makedirs(target_dir, exist_ok=True)

    # 提取文件名与后缀
    base_name = os.path.basename(original_filename or "document")
    stem, ext = os.path.splitext(base_name)
    safe_stem = sanitize_segment(stem, default="document")
    safe_ext = ext.lower()

    # 处理重名：若目标文件已存在，则自动递增数字后缀 (1), (2)...
    final_filename = f"{safe_stem}{safe_ext}"
    target_file_path = os.path.join(target_dir, final_filename)

    counter = 1
    while os.path.exists(target_file_path):
        final_filename = f"{safe_stem}({counter}){safe_ext}"
        target_file_path = os.path.join(target_dir, final_filename)
        counter += 1

    # 生成 URL 访问路径 (统一以 /uploads/ 开头)
    raw_file_url = f"/uploads/{safe_user}/{safe_doc}/{date_str}/{final_filename}"

    return target_file_path, raw_file_url, final_filename


def compress_image_for_ai(file_bytes: bytes) -> bytes:
    """
    压缩图片用于发送给 AI，限制最大边长为 2000px，转为 JPEG 以节省带宽和加快传输。
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))
        # 转换 RGBA 或 P 模式到 RGB
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # 限制最大边长 2000
        max_size = 2000
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
        out_io = io.BytesIO()
        img.save(out_io, format="JPEG", quality=85)
        return out_io.getvalue()
    except Exception as e:
        # 如果不是图片（如 PDF）或压缩失败，原样返回
        return file_bytes

async def process_single_file(sem: asyncio.Semaphore, task_id: str, idx: int, f_info: dict, doc_type: str):
    # 错峰起跑，每隔 1.5 秒放行一个任务，避免瞬间并发击穿 sub2api 代理服务器的 token 锁
    await asyncio.sleep(idx * 1.5)
    
    async with sem:
        db = SessionLocal()
        try:
            file_path = f_info["file_path"]
            mime_type = f_info["mime_type"]
            filename = f_info["filename"]
            raw_url = f_info["raw_file_url"]

            with open(file_path, "rb") as f:
                file_bytes = f.read()

            # 针对图片进行压缩，极大减少大模型 API 网络传输耗时
            if mime_type.startswith("image/"):
                ai_bytes = compress_image_for_ai(file_bytes)
                ai_mime_type = "image/jpeg"
            else:
                ai_bytes = file_bytes
                ai_mime_type = mime_type

            extracted_data = await ai_extractor.analyze_document(ai_bytes, ai_mime_type, doc_type, db=db)
            
            batch_tasks[task_id]["results"].append({
                "success": True,
                "filename": filename,
                "raw_file_url": raw_url,
                "doc_type": doc_type,
                "parsed_data": extracted_data,
                "original_index": idx
            })
        except Exception as e:
            import logging
            logging.error(f"File {filename} parse error: {str(e)}")
            batch_tasks[task_id]["errors"].append(f"文件 {filename} 解析失败")
        finally:
            batch_tasks[task_id]["completed"] += 1
            db.close()

async def process_batch_task(task_id: str, files_info: List[dict], doc_type: str):
    """
    后台任务：并发控制的协程任务组，加速处理
    """
    try:
        # 并发度设置为 3，既能大幅提速，又能避免单点击穿中转站并发锁
        sem = asyncio.Semaphore(3)
        tasks = [
            process_single_file(sem, task_id, idx, f_info, doc_type)
            for idx, f_info in enumerate(files_info)
        ]
        await asyncio.gather(*tasks)
        batch_tasks[task_id]["status"] = "completed"
    except Exception as e:
        import logging
        logging.error(f"Batch task fatal error: {str(e)}")
        batch_tasks[task_id]["status"] = "error"
        batch_tasks[task_id]["errors"].append(f"批量解析任务异常中止")


@router.post("/parse-batch")
async def upload_and_parse_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    doc_type: str = Form("lab"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="一次最多支持上传 10 个文件，请分批上传。")

    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".bmp"}
    
    files_info = []
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_extensions:
            continue
        
        file_path, raw_file_url, final_filename = prepare_upload_target(
            username=current_user.username,
            doc_type=doc_type,
            original_filename=file.filename
        )
        
        file_bytes = await file.read()
        with open(file_path, "wb") as f:
            f.write(file_bytes)
            
        files_info.append({
            "filename": final_filename,
            "file_path": file_path,
            "raw_file_url": raw_file_url,
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

    file_path, raw_file_url, final_filename = prepare_upload_target(
        username=current_user.username,
        doc_type=doc_type,
        original_filename=file.filename
    )
    
    file_bytes = await file.read()
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    mime_type = file.content_type or "image/jpeg"
    
    if mime_type.startswith("image/"):
        ai_bytes = compress_image_for_ai(file_bytes)
        ai_mime_type = "image/jpeg"
    else:
        ai_bytes = file_bytes
        ai_mime_type = mime_type

    extracted_data = await ai_extractor.analyze_document(ai_bytes, ai_mime_type, doc_type, db=db)

    return {
        "success": True,
        "filename": final_filename,
        "raw_file_url": raw_file_url,
        "doc_type": doc_type,
        "parsed_data": extracted_data
    }
