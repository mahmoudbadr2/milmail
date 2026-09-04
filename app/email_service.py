import secrets
import string
import httpx
from typing import Optional, Tuple
from app.config import settings

def generate_random_alias(prefix: Optional[str] = None) -> str:
    """
    توليد اسم بريد مستعار آمن وعشوائي يصعب تخمينه
    مثال: shopping.8k2m9x@minmail.pro
    """
    random_str = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    if prefix:
        # تعقيم البادئة من أي رموز غير مرغوبة
        clean_prefix = ''.join(c for c in prefix.lower() if c.isalnum() or c in ['-', '_'])[:15]
        if clean_prefix:
            return f"{clean_prefix}.{random_str}@{settings.DOMAIN}"
    return f"alias.{random_str}@{settings.DOMAIN}"

async def sync_cloudflare_rule(alias_email: str, destination_email: str, is_active: bool = True) -> Tuple[bool, Optional[str]]:
    """
    مزامنة قاعدة التوجيه مع Cloudflare Email Routing API
    إذا لم تتوفر مفاتيح API، يعمل في وضع المحاكاة الآمنة (Local Emulation Mode)
    """
    if not settings.CLOUDFLARE_API_TOKEN or not settings.CLOUDFLARE_ZONE_ID:
        # وضع التشغيل المحلي / التجريبي دون خطأ
        return True, f"mock_rule_{secrets.token_hex(6)}"

    url = f"https://api.cloudflare.com/client/v4/zones/{settings.CLOUDFLARE_ZONE_ID}/email/routing/rules"
    headers = {
        "Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "matchers": [{"type": "literal", "field": "to", "value": alias_email}],
        "actions": [{"type": "forward", "value": [destination_email]}],
        "name": f"MinMail Alias: {alias_email}",
        "enabled": is_active
    }

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, headers=headers, timeout=10.0)
            data = res.json()
            if data.get("success"):
                rule_id = data["result"]["id"]
                return True, rule_id
            return False, data.get("errors", [{}])[0].get("message", "فشل إنشاء قاعدة التحويل")
    except Exception as e:
        return False, str(e)

async def toggle_cloudflare_rule(rule_id: str, is_active: bool) -> bool:
    """تفعيل أو تعطيل قاعدة توجيه فوراً عبر Cloudflare"""
    if not settings.CLOUDFLARE_API_TOKEN or not settings.CLOUDFLARE_ZONE_ID or not rule_id or rule_id.startswith("mock_"):
        return True

    url = f"https://api.cloudflare.com/client/v4/zones/{settings.CLOUDFLARE_ZONE_ID}/email/routing/rules/{rule_id}"
    headers = {
        "Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            res = await client.patch(url, json={"enabled": is_active}, headers=headers, timeout=10.0)
            return res.json().get("success", False)
    except Exception:
        return False

async def delete_cloudflare_rule(rule_id: str) -> bool:
    """حذف قاعدة توجيه من Cloudflare تماماً"""
    if not settings.CLOUDFLARE_API_TOKEN or not settings.CLOUDFLARE_ZONE_ID or not rule_id or rule_id.startswith("mock_"):
        return True

    url = f"https://api.cloudflare.com/client/v4/zones/{settings.CLOUDFLARE_ZONE_ID}/email/routing/rules/{rule_id}"
    headers = {
        "Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}"
    }

    try:
        async with httpx.AsyncClient() as client:
            res = await client.delete(url, headers=headers, timeout=10.0)
            return res.json().get("success", False)
    except Exception:
        return False
