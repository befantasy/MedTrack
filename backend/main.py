import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import engine, Base
import models
from routers import (
    auth_router,
    oncology_router,
    lab_router,
    imaging_router,
    upload_router,
    chart_router,
    share_router,
    admin_router
)
from sqlalchemy.orm import Session
from auth import hash_password

# 自动创建全部数据库表结构
Base.metadata.create_all(bind=engine)

# 自动播种初始超级管理员账号
def init_system_defaults():
    try:
        with Session(engine) as db:
            admin_user = db.query(models.User).filter(models.User.is_admin == True).first()
            if not admin_user and settings.ADMIN_USERNAME:
                hashed = hash_password(settings.ADMIN_PASSWORD)
                new_admin = models.User(
                    username=settings.ADMIN_USERNAME,
                    password_hash=hashed,
                    is_admin=True,
                    is_active=True
                )
                db.add(new_admin)
                db.commit()
                db.refresh(new_admin)

                profile = models.CancerProfile(
                    user_id=new_admin.id,
                    patient_name="系统管理员",
                    primary_site="未录入",
                    pathology_type="未录入",
                    current_staging="管理归档"
                )
                db.add(profile)
                db.commit()
    except Exception as e:
        print(f"Warning: init_system_defaults failed: {e}")

init_system_defaults()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url=f"{settings.API_V1_STR}/docs",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 允许跨域（前端容器与后端同域或异域开发均无缝运行）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载上传文件静态目录
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# 挂载路由模块
app.include_router(auth_router.router, prefix=settings.API_V1_STR)
app.include_router(oncology_router.router, prefix=settings.API_V1_STR)
app.include_router(lab_router.router, prefix=settings.API_V1_STR)
app.include_router(imaging_router.router, prefix=settings.API_V1_STR)
app.include_router(upload_router.router, prefix=settings.API_V1_STR)
app.include_router(chart_router.router, prefix=settings.API_V1_STR)
app.include_router(share_router.router, prefix=settings.API_V1_STR)
app.include_router(admin_router.router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "database": settings.DATABASE_URL.split("://")[0]
    }

# 挂载前端静态页面与资源 (一体化单镜像，无需独立 Nginx)
frontend_candidates = [
    os.path.join(os.path.dirname(__file__), "frontend"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend"),
    "/app/frontend",
]
frontend_dir = next((p for p in frontend_candidates if os.path.isdir(p)), None)
if frontend_dir:
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

