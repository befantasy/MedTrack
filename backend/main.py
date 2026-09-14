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
    share_router
)

# 自动创建全部数据库表结构
Base.metadata.create_all(bind=engine)

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

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "database": settings.DATABASE_URL.split("://")[0]
    }
