import smtplib
import urllib.parse
import webbrowser
from email.mime.text import MIMEText

# 实际应用中，联系人信息应从数据库或配置文件读取
CONTACTS = {
    "周总": "zhouzong@163.com",
    "李经理": "li@gmail.com"
}


def atomic_result(success, message, **kwargs):
    """
    一个更灵活的结果生成器。

    Args:
        success (bool): 操作是否成功。
        message (str): 操作结果的消息。
        **kwargs: 任意数量的关键字参数，将作为返回字典的核心数据。
                  例如: found_files=["path1", "path2"]

    Returns:
        dict: 一个包含执行状态和所有传入数据的字典。
    """
    result = {
        "success": success,
        "message": message
    }
    # 将所有传入的关键字参数合并到结果字典中
    result.update(kwargs)
    return result

def get_contact_email(contact_name: str):
    email = CONTACTS.get(contact_name)
    if email:
        return atomic_result(True, f"成功找到联系人 {contact_name} 的邮箱", email=email)
    else:
        return atomic_result(False, f"未在通讯录中找到联系人: {contact_name}")

def compose_email(recipient_email: str, subject: str, body: str, attachment_path: str):
    """
    调用系统的默认邮件客户端，并预先填好收件人、主题、正文。
    注意：标准的 mailto: URI 方案不支持直接添加附件，
    因此此函数的功能是打开邮件草稿，并告知用户需要手动添加附件。
    """
    try:
        # 使用 urllib.parse.quote 对主题和正文进行URL编码，以正确处理空格、换行符和特殊字符
        encoded_subject = urllib.parse.quote(subject)
        encoded_body = urllib.parse.quote(body)

        # 构造 mailto: 链接
        # 注意：正文中我们加入一条提示，提醒用户添加附件
        user_prompt_body = f"""{body}

---------------------------------
(此邮件由 DeepShell 自动生成)
请手动添加附件: {attachment_path}
"""
        encoded_body_with_prompt = urllib.parse.quote(user_prompt_body)

        mailto_url = f"mailto:{recipient_email}?subject={encoded_subject}&body={encoded_body_with_prompt}"

        # 使用 webbrowser 模块打开链接，这将启动用户的默认邮件程序
        webbrowser.open(mailto_url)

        message = f"已打开邮件客户端。请检查草稿，手动附加文件 '{attachment_path}'，然后点击发送。"
        return atomic_result(True, message)

    except Exception as e:
        return atomic_result(False, f"打开邮件客户端失败: {e}")


FUNCTION_MAP = {
    "get_contact_email": get_contact_email,
    "compose_email": compose_email
}
