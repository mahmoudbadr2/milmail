import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # إعدادات النظام والدومين
    PROJECT_NAME: str = "MinMail - Privacy Email Alias"
    DOMAIN: str = "minmail.pro"
    
    # الأمان والمصادقة
    SECRET_KEY: str = os.getenv("SECRET_KEY", "minmail_super_secret_secure_key_change_in_production_2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # أسبوع كامل للجلسة
    
    # حدود الخطط (Plans Limits)
    FREE_ALIASES_LIMIT: int = 2  # تعديل إلى 2 إيميل فقط للباقة المجانية
    PRO_ALIASES_LIMIT: int = 999999  # غير محدود لـ Pro
    PRO_MONTHLY_PRICE: float = 2.99
    
    # تسجيل الدخول عبر Google
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID", "")
    
    # إعدادات Cloudflare Email Routing API
    CLOUDFLARE_API_TOKEN: Optional[str] = os.getenv("CLOUDFLARE_API_TOKEN", "")
    CLOUDFLARE_ZONE_ID: Optional[str] = os.getenv("CLOUDFLARE_ZONE_ID", "")
    
    # مفاتيح الدفع (Stripe أو LemonSqueezy)
    STRIPE_SECRET_KEY: Optional[str] = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: Optional[str] = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    # إعدادات الإعلانات
    ENABLE_ADS_FOR_FREE: bool = True
    ADSENSE_CLIENT_ID: Optional[str] = os.getenv("ADSENSE_CLIENT_ID", "ca-pub-XXXXXXXXXXXXXXXX")
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
