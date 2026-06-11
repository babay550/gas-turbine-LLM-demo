"""密码工具 — bcrypt 哈希与验证。"""

import bcrypt


def hash_password(password: str) -> str:
    """生成密码的 bcrypt 哈希。"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码是否匹配哈希。"""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
