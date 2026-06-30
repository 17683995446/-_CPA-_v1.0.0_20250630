"""
密码安全模块。

架构规范：
- 使用 bcrypt 加 salt 哈希，替代不安全的裸 sha256
- 提供统一的 hash_password / verify_password 接口
- 向后兼容：能验证旧的 sha256 哈希（迁移期间）
"""
import hashlib

import bcrypt


def hash_password(password: str) -> str:
    """使用 bcrypt 对密码进行加盐哈希。"""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    验证密码是否匹配。

    向后兼容：先尝试 bcrypt，若哈希长度为 64（sha256 hexdigest）则回退到旧逻辑。
    """
    # bcrypt 哈希以 $2b$ 开头
    if password_hash.startswith("$2"):
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                password_hash.encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False

    # 兼容旧的 sha256 哈希（迁移期间）
    if len(password_hash) == 64:
        return hashlib.sha256(password.encode("utf-8")).hexdigest() == password_hash

    return False
