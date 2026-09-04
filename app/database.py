import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# في بيئة Vercel السحابية، مجلد /tmp هو الوحيد المتاح للكتابة
if os.environ.get("VERCEL"):
    DATABASE_URL = "sqlite:////tmp/minmail.db"
else:
    DATABASE_URL = "sqlite:///./minmail.db"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # تفاصيل العضوية (Pro Tier)
    is_pro = Column(Boolean, default=False)
    pro_expires_at = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    
    # حالة الحساب
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # العلاقات
    aliases = relationship("EmailAlias", back_populates="owner", cascade="all, delete-orphan")

class EmailAlias(Base):
    __tablename__ = "email_aliases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # البريد المستعار والبريد الحقيقي
    alias_email = Column(String, unique=True, index=True, nullable=False) # e.g. shop.xyz8@minmail.pro
    destination_email = Column(String, nullable=False) # البريد الحقيقي للمستخدم
    
    # وصف أو تصنيف للألياس (مثلاً: للتسجيل في نتفلكس)
    description = Column(String, default="")
    
    # تفعيل أو تعطيل التوجيه لحظياً بضغطة زر
    is_active = Column(Boolean, default=True)
    
    # معرف قاعدة التوجيه في Cloudflare إن وُجد
    cloudflare_rule_id = Column(String, nullable=True)
    
    # إحصائيات
    emails_forwarded_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="aliases")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
