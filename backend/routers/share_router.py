import datetime
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import get_current_user
from services.report_generator import report_generator

router = APIRouter(prefix="/share", tags=["病历报告生成与安全外链分享"])

@router.get("/my-report")
def get_my_consultation_report(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """当前登录用户预览自己的一键专科门诊/MDT病历汇总报告"""
    return report_generator.generate_consultation_report(current_user.id, db)

@router.post("/create-link", response_model=schemas.ShareLinkOut)
def create_share_link(
    link_in: schemas.ShareLinkCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """为患者生成加密专属只读分享链接 (供医生或家属查阅，支持设置有效期与4位提取码)"""
    token = uuid.uuid4().hex
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=link_in.expire_days)

    share_link = models.ShareLink(
        user_id=current_user.id,
        share_token=token,
        access_code=link_in.access_code.strip() if link_in.access_code else "",
        expires_at=expires_at,
        is_active=True
    )
    db.add(share_link)
    db.commit()
    db.refresh(share_link)

    return {
        "share_token": token,
        "share_url": f"/share.html?token={token}",
        "access_code": share_link.access_code or None,
        "expires_at": expires_at
    }

@router.get("/view/{share_token}")
def view_shared_report(
    share_token: str,
    code: Optional[str] = Query(None, description="访问提取码"),
    db: Session = Depends(get_db)
):
    """
    医生/外部人员只读访问端 (免登录)，输入有效链接即可查看完整汇总
    """
    share_link = db.query(models.ShareLink).filter(
        models.ShareLink.share_token == share_token,
        models.ShareLink.is_active == True
    ).first()

    if not share_link:
        raise HTTPException(status_code=404, detail="分享链接不存在或已被关闭")

    if share_link.expires_at < datetime.datetime.utcnow():
        raise HTTPException(status_code=410, detail="该就诊病历分享链接已过期")

    # 如果设置了访问密码/提取码
    if share_link.access_code:
        if not code or code.strip() != share_link.access_code:
            return {
                "need_code": True,
                "message": "该病历报告受保护，请输入 4 位访问提取码"
            }

    # 密码验证通过或无需密码，生成只读病历报告
    report_data = report_generator.generate_consultation_report(share_link.user_id, db)
    return {
        "need_code": False,
        "report": report_data,
        "expires_at": share_link.expires_at.strftime("%Y-%m-%d %H:%M")
    }
