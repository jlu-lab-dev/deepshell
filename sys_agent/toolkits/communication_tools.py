# sys_agent/toolkits/communication_tools.py
"""
通讯工具集。
提供邮件发送相关的联系人查询和邮件草稿创建功能。
"""

from __future__ import annotations

import urllib.parse
import webbrowser
from typing import Any

from ._base import ok, fail, require_non_empty

# 联系人通讯录（可扩展为数据库或配置文件读取）
CONTACTS: dict[str, str] = {
    "周总": "zhouzong@163.com",
    "李经理": "li@gmail.com",
}


def get_contact_email(contact_name: str) -> dict[str, Any]:
    """根据联系人姓名查询邮箱地址。"""
    try:
        require_non_empty(contact_name, "contact_name")
        email = CONTACTS.get(contact_name)
        if email:
            return ok(f"查询到 {contact_name} 的邮箱", email=email)
        known = ", ".join(CONTACTS.keys()) or "（暂无）"
        return fail(f"未在通讯录中找到联系人: {contact_name}。当前已知联系人: {known}")
    except ValueError as e:
        return fail(f"参数错误: {e}")


def compose_email(
    recipient_email: str,
    subject: str,
    body: str,
    attachment_path: str,
) -> dict[str, Any]:
    """打开邮件客户端创建预填草稿，提示用户添加附件。"""
    try:
        require_non_empty(recipient_email, "recipient_email")
        require_non_empty(subject, "subject")
        require_non_empty(body, "body")
        require_non_empty(attachment_path, "attachment_path")

        # 自动补充附件说明
        body_with_note = f"""{body}

---
（此邮件由 DeepShell 自动生成）
请手动添加附件: {attachment_path}
"""
        params = urllib.parse.urlencode({
            "subject": subject,
            "body": body_with_note,
        })
        mailto = f"mailto:{recipient_email}?{params}"
        webbrowser.open(mailto)
        return ok(
            f"邮件草稿已创建。请在邮件客户端中检查并添加附件 '{attachment_path}' 后发送。",
            recipient=recipient_email,
            subject=subject,
            attachment_note=attachment_path,
        )
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except Exception as e:
        return fail(f"打开邮件客户端失败: {e}")


FUNCTION_MAP: dict[str, callable] = {
    "get_contact_email": get_contact_email,
    "compose_email": compose_email,
}
