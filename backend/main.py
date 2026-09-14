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
from sqlalchemy import text
from auth import hash_password

# 自动无损增量迁移数据库字段 (兼容已有持久化卷)
def auto_migrate_db():
    try:
        with engine.connect() as conn:
            # 1. 自动为 users 表补充 is_admin 与 is_active 字段
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
            except Exception as e:
                print(f"Users table migration note: {e}")

            # 2. 自动补充 system_settings 表
            try:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS system_settings (
                        key VARCHAR(64) PRIMARY KEY,
                        value TEXT NOT NULL,
                        description VARCHAR(256) DEFAULT '',
                        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """))
            except Exception as e:
                print(f"System settings table migration note: {e}")
            conn.commit()
    except Exception as e:
        print(f"Auto-migration db note: {e}")

auto_migrate_db()

# 自动创建全部新数据库表结构
Base.metadata.create_all(bind=engine)

# 预设系统默认超级管理员 (开箱即用: admin / admin)
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"

# 自动播种并校准超级管理员账号
def init_system_defaults():
    try:
        with Session(engine) as db:
            # 1. 确保全局注册开关设置存在
            reg_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "allow_registration").first()
            if not reg_setting:
                db.add(models.SystemSetting(key="allow_registration", value="true", description="允许新用户公开自主注册"))
                db.commit()

            # 2. 预设超级管理员账号 (admin / admin)
            existing_target = db.query(models.User).filter(models.User.username == DEFAULT_ADMIN_USERNAME).first()

            if existing_target:
                existing_target.is_admin = True
                existing_target.is_active = True
                # 若此前残留的是旧版本初始密码 admin123456，自动校准为新的预设默认密码 admin
                if verify_password("admin123456", existing_target.password_hash):
                    existing_target.password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
                db.commit()
            else:
                hashed = hash_password(DEFAULT_ADMIN_PASSWORD)
                new_admin = models.User(
                    username=DEFAULT_ADMIN_USERNAME,
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

            # 3. 兜底保护：若系统中没有任何账号是管理员，自动提拔最早注册的账号为管理员
            any_admin = db.query(models.User).filter(models.User.is_admin == True).first()
            if not any_admin:
                first_u = db.query(models.User).order_by(models.User.id.asc()).first()
                if first_u:
                    first_u.is_admin = True
                    first_u.is_active = True
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

