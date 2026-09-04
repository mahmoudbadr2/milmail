import datetime
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.config import settings
from app.database import init_db, get_db, User, EmailAlias
from app.security import (
    verify_password, get_password_hash, create_access_token, 
    get_current_user, require_current_user
)
from app.email_service import (
    generate_random_alias, sync_cloudflare_rule, 
    toggle_cloudflare_rule, delete_cloudflare_rule
)

# إنشاء محدد المعدل للحماية من هجمات الإغراق (Rate Limiting)
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title=settings.PROJECT_NAME)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ربط الملفات الثابتة والقوالب
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
def on_startup():
    init_db()

# ترويسات الأمان المتقدمة (Security Headers Middleware)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# ===== واجهات الويب (Web UI Routes) =====

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, user: Optional[User] = Depends(get_current_user)):
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "user": user, 
        "settings": settings
    })

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: Optional[User] = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request, "settings": settings})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user: Optional[User] = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("register.html", {"request": request, "settings": settings})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request, 
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    aliases = db.query(EmailAlias).filter(EmailAlias.user_id == user.id).order_by(EmailAlias.created_at.desc()).all()
    aliases_count = len(aliases)
    limit = settings.PRO_ALIASES_LIMIT if user.is_pro else settings.FREE_ALIASES_LIMIT
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "aliases": aliases,
        "aliases_count": aliases_count,
        "aliases_limit": limit,
        "can_create_more": aliases_count < limit,
        "settings": settings
    })

# ===== واجهات المصادقة (Authentication API) =====

@app.post("/api/auth/register")
@limiter.limit("5/minute")
async def api_register(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    email = email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="هذا البريد الإلكتروني مسجل بالفعل مسبقاً")
        
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 8 أحرف على الأقل")
        
    new_user = User(
        email=email,
        hashed_password=get_password_hash(password),
        is_pro=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # إنشاء توكن وتسجيل الدخول فوراً
    token = create_access_token({"sub": new_user.email})
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=604800, samesite="lax")
    return {"status": "success", "redirect": "/dashboard"}

@app.post("/api/auth/login")
@limiter.limit("10/minute")
async def api_login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="بيانات الدخول غير صحيحة")

    token = create_access_token({"sub": user.email})
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=604800, samesite="lax")
    return {"status": "success", "redirect": "/dashboard"}

@app.get("/logout")
async def logout():
    res = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    res.delete_cookie("access_token")
    return res

@app.post("/api/auth/google")
async def api_google_login(
    request: Request,
    response: Response,
    credential: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    تسجيل الدخول التلقائي والمباشر عبر Google (Google One Tap / Sign In)
    """
    try:
        # فك تشفير وتدقيق التوكن القادم من جوجل
        async with httpx.AsyncClient() as client:
            res = await client.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}")
            if res.status_code != 200:
                raise HTTPException(status_code=400, detail="فشل التحقق من صحة حساب Google")
            payload = res.json()
            google_email = payload.get("email")
            if not google_email:
                raise HTTPException(status_code=400, detail="لم يتم العثور على بريد إلكتروني في حساب Google")
                
            google_email = google_email.lower().strip()
            
            # فحص إذا كان المستخدم موجود مسبقاً أو إنشاء حساب جديد له فوراً
            user = db.query(User).filter(User.email == google_email).first()
            if not user:
                user = User(
                    email=google_email,
                    hashed_password=get_password_hash("GOOGLE_SSO_USER_" + google_email),
                    is_pro=False
                )
                db.add(user)
                db.commit()
                db.refresh(user)

            # إنشاء توكن الجلسة وتخزينه في الكوكي الآمنة
            token = create_access_token({"sub": user.email})
            response.set_cookie(key="access_token", value=token, httponly=True, max_age=604800, samesite="lax")
            return {"status": "success", "redirect": "/dashboard"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"حدث خطأ أثناء الاتصال بجوجل: {str(e)}")

# ===== واجهات إدارة الأسماء المستعارة (Aliases API) =====

@app.post("/api/aliases/create")
@limiter.limit("20/minute")
async def api_create_alias(
    request: Request,
    description: str = Form(""),
    prefix: Optional[str] = Form(None),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    current_count = db.query(EmailAlias).filter(EmailAlias.user_id == user.id).count()
    limit = settings.PRO_ALIASES_LIMIT if user.is_pro else settings.FREE_ALIASES_LIMIT
    
    if current_count >= limit:
        raise HTTPException(
            status_code=403, 
            detail=f"لقد وصلت للحد الأقصى في الخطة المجانية ({limit} إيميلات). قم بالترقية إلى Pro للحصول على عدد غير محدود!"
        )

    # توليد الإيميل المستعار
    alias_email = generate_random_alias(prefix)
    
    # مزامنة القاعدة مع Cloudflare
    success, rule_id = await sync_cloudflare_rule(alias_email, user.email, is_active=True)
    
    new_alias = EmailAlias(
        user_id=user.id,
        alias_email=alias_email,
        destination_email=user.email,
        description=description.strip() or "عام",
        is_active=True,
        cloudflare_rule_id=rule_id if success else None
    )
    db.add(new_alias)
    db.commit()
    db.refresh(new_alias)
    
    return {
        "status": "success", 
        "alias": {
            "id": new_alias.id,
            "email": new_alias.alias_email,
            "description": new_alias.description,
            "created_at": new_alias.created_at.strftime("%Y-%m-%d")
        }
    }

@app.post("/api/aliases/{alias_id}/toggle")
async def api_toggle_alias(
    alias_id: int,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    alias = db.query(EmailAlias).filter(EmailAlias.id == alias_id, EmailAlias.user_id == user.id).first()
    if not alias:
        raise HTTPException(status_code=404, detail="البريد المستعار غير موجود")

    new_state = not alias.is_active
    alias.is_active = new_state
    
    if alias.cloudflare_rule_id:
        await toggle_cloudflare_rule(alias.cloudflare_rule_id, new_state)
        
    db.commit()
    return {"status": "success", "is_active": new_state}

@app.delete("/api/aliases/{alias_id}")
async def api_delete_alias(
    alias_id: int,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    alias = db.query(EmailAlias).filter(EmailAlias.id == alias_id, EmailAlias.user_id == user.id).first()
    if not alias:
        raise HTTPException(status_code=404, detail="البريد المستعار غير موجود")

    if alias.cloudflare_rule_id:
        await delete_cloudflare_rule(alias.cloudflare_rule_id)
        
    db.delete(alias)
    db.commit()
    return {"status": "success"}

# ===== واجهة الترقية إلى Pro (Upgrade Tier) =====

@app.post("/api/user/upgrade-pro")
async def api_upgrade_pro(
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    تفعيل عضوية Pro (إزالة الإعلانات والحصول على إيميلات غير محدودة)
    مهيأة للربط المباشر مع بوابات الدفع
    """
    user.is_pro = True
    user.pro_expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=365)
    db.commit()
    return {"status": "success", "message": "تمت ترقية حسابك إلى باقة Pro بنجاح! استمتع بإيميلات غير محدودة وبدون أي إعلانات."}
