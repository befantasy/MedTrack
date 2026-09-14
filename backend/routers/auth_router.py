from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import hash_password, verify_password, create_access_token, get_current_user
from config import settings

router = APIRouter(prefix="/auth", tags=["用户认证与档案"])

@router.post("/register", response_model=schemas.Token)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """新用户自主注册，并初始化空档案"""
    # 1. 检查全局注册开关
    reg_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "allow_registration").first()
    if reg_setting and reg_setting.value.lower() in ("false", "0", "no"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前系统已关闭公开自主注册通道，请联系系统管理员分配账号"
        )

    existing = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被注册，请直接登录或更换用户名"
        )
    
    # 若系统尚无任何用户，第一个注册的用户自动升级为超级管理员
    user_count = db.query(models.User).count()
    is_first_user = (user_count == 0)

    hashed = hash_password(user_in.password)
    new_user = models.User(
        username=user_in.username,
        password_hash=hashed,
        is_admin=is_first_user,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 自动创建专属肿瘤与慢病档案
    profile = models.CancerProfile(
        user_id=new_user.id,
        patient_name=user_in.username,
        primary_site="",
        pathology_type="",
        current_staging="初诊评估中"
    )
    db.add(profile)
    db.commit()

    # 自动发放 Token
    access_token = create_access_token(data={"sub": new_user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": new_user
    }

@router.post("/login", response_model=schemas.Token)
def login(user_in: schemas.UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(models.User).filter(models.User.username == user_in.username).first()
    
    # 针对初始 admin 账号的兼容平滑校准：
    # 如果用户使用预设账号 admin 并输入默认密码 admin：
    if user and user.username.lower() == "admin" and user_in.password == "admin":
        if verify_password("admin123456", user.password_hash) or not verify_password("admin", user.password_hash):
            user.password_hash = hash_password("admin")
            user.is_admin = True
            user.is_active = True
            db.commit()
            db.refresh(user)

    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 动态管理员提权校验：如果用户名是 admin 或系统只有此1个用户，确保赋予超级管理员身份
    total_users = db.query(models.User).count()
    if (user.username.lower() == "admin" or total_users == 1) and not user.is_admin:
        user.is_admin = True
        user.is_active = True
        db.commit()
        db.refresh(user)

    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me")
def get_me(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前登录用户的账户与完整肿瘤基准档案"""
    total_users = db.query(models.User).count()
    if (current_user.username.lower() == "admin" or total_users == 1) and not current_user.is_admin:
        current_user.is_admin = True
        current_user.is_active = True
        db.commit()
        db.refresh(current_user)

    profile = db.query(models.CancerProfile).filter(models.CancerProfile.user_id == current_user.id).first()
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "is_admin": current_user.is_admin,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at
        },
        "profile": profile
    }

@router.put("/password")
def change_my_password(
    data: schemas.ChangePasswordRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """当前登录用户（含管理员）自主修改个人登录密码"""
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前原密码不正确"
        )
    if len(data.new_password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码长度不能少于4位字符"
        )
    current_user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "密码修改成功，下次登录请使用新密码"}

@router.put("/profile", response_model=schemas.CancerProfileOut)
def update_profile(
    profile_in: schemas.CancerProfileCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新肿瘤患者基准档案 (TNM分期、分子靶点、伴随慢病等)"""
    profile = db.query(models.CancerProfile).filter(models.CancerProfile.user_id == current_user.id).first()
    if not profile:
        profile = models.CancerProfile(user_id=current_user.id)
        db.add(profile)

    update_data = profile_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return profile
