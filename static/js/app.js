// MinMail Interactive Operations

async function copyToClipboard(text, btnElement) {
    try {
        await navigator.clipboard.writeText(text);
        const originalText = btnElement.innerHTML;
        btnElement.innerHTML = `<svg class="w-4 h-4 inline mr-1 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg> تم النسخ!`;
        setTimeout(() => {
            btnElement.innerHTML = originalText;
        }, 2000);
    } catch (err) {
        alert("فشل النسخ تلقائياً، يرجى نسخه يدوياً: " + text);
    }
}

async function createAlias() {
    const prefix = document.getElementById('aliasPrefix').value.trim();
    const description = document.getElementById('aliasDescription').value.trim();
    const createBtn = document.getElementById('createAliasBtn');

    createBtn.disabled = true;
    createBtn.innerHTML = `جاري التوليد...`;

    const formData = new FormData();
    if (prefix) formData.append('prefix', prefix);
    if (description) formData.append('description', description);

    try {
        const response = await fetch('/api/aliases/create', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (response.ok) {
            window.location.reload();
        } else {
            alert(data.detail || "حدث خطأ أثناء إنشاء البريد المستعار");
        }
    } catch (error) {
        alert("تعذر الاتصال بالخادم، يرجى المحاولة مرة أخرى.");
    } finally {
        createBtn.disabled = false;
        createBtn.innerHTML = `توليد بريد مستعار جديد`;
    }
}

async function toggleAlias(aliasId, currentStatus) {
    try {
        const response = await fetch(`/api/aliases/${aliasId}/toggle`, {
            method: 'POST'
        });
        if (response.ok) {
            window.location.reload();
        } else {
            alert("فشل تغيير حالة التوجيه");
        }
    } catch (error) {
        alert("حدث خطأ في الاتصال");
    }
}

async function deleteAlias(aliasId) {
    if (!confirm("هل أنت متأكد من حذف هذا البريد المستعار؟ لن تتمكن من استلام أي رسائل موجهة إليه بعد الآن.")) {
        return;
    }

    try {
        const response = await fetch(`/api/aliases/${aliasId}`, {
            method: 'DELETE'
        });
        if (response.ok) {
            window.location.reload();
        } else {
            alert("فشل حذف البريد المستعار");
        }
    } catch (error) {
        alert("حدث خطأ في الاتصال");
    }
}

async function upgradeToPro() {
    if (!confirm("هل تود تفعيل ترقية باقة Pro الآن للاستمتاع بإيميلات غير محدودة وإزالة الإعلانات بالكامل؟")) {
        return;
    }

    try {
        const response = await fetch('/api/user/upgrade-pro', {
            method: 'POST'
        });
        const data = await response.json();
        if (response.ok) {
            alert(data.message);
            window.location.reload();
        }
    } catch (error) {
        alert("تعذر إتمام الترقية حالياً");
    }
}
