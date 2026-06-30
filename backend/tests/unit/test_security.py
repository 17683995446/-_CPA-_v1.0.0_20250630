"""
密码安全模块单元测试。

验证规范：
- bcrypt 哈希以 $2b$ 开头
- 相同密码每次哈希结果不同（salt 随机）
- verify_password 正确验证 bcrypt 和旧 sha256 哈希
- 错误密码返回 False
"""
import hashlib

from app.security import hash_password, verify_password


class TestHashPassword:
    def test_bcrypt_format(self):
        """哈希结果应以 $2b$ 开头。"""
        h = hash_password("mypassword")
        assert h.startswith("$2b$")

    def test_different_salt_each_time(self):
        """相同密码每次哈希结果不同。"""
        h1 = hash_password("test123")
        h2 = hash_password("test123")
        assert h1 != h2

    def test_empty_password(self):
        """空密码也能正常哈希。"""
        h = hash_password("")
        assert h.startswith("$2b$")


class TestVerifyPassword:
    def test_correct_bcrypt(self):
        """正确密码验证通过。"""
        h = hash_password("secret123")
        assert verify_password("secret123", h) is True

    def test_wrong_bcrypt(self):
        """错误密码验证失败。"""
        h = hash_password("secret123")
        assert verify_password("wrong", h) is False

    def test_legacy_sha256_compat(self):
        """兼容旧 sha256 哈希。"""
        legacy = hashlib.sha256("oldpass".encode()).hexdigest()
        assert verify_password("oldpass", legacy) is True
        assert verify_password("wrong", legacy) is False

    def test_invalid_hash_format(self):
        """无效哈希格式返回 False。"""
        assert verify_password("test", "invalid") is False
        assert verify_password("test", "") is False
