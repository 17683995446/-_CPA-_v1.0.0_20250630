"""
错误码体系与中间件单元测试。

验证规范：
- ErrorCode 枚举值符合编码规则
- BusinessException 正确携带错误码和 HTTP 状态码
- DEFAULT_ERROR_MESSAGES 覆盖所有错误码
- 请求追踪中间件生成并返回 X-Request-ID
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import DEFAULT_ERROR_MESSAGES, ErrorCode, BusinessException
from app.middleware import REQUEST_ID_HEADER, RequestIdMiddleware, register_middleware


class TestErrorCode:
    """错误码枚举验证。"""

    def test_error_codes_are_unique(self):
        values = [e.value for e in ErrorCode]
        assert len(values) == len(set(values))

    def test_error_code_to_http_status(self):
        """错误码前3位应对应 HTTP 状态码。"""
        assert ErrorCode.INVALID_PARAMS // 100 == 400
        assert ErrorCode.RESOURCE_NOT_FOUND // 100 == 404
        assert ErrorCode.USER_ALREADY_EXISTS // 100 == 409
        assert ErrorCode.INTERNAL_ERROR // 100 == 500

    def test_all_error_codes_have_default_messages(self):
        """每个错误码都应有默认消息。"""
        for code in ErrorCode:
            assert code in DEFAULT_ERROR_MESSAGES, f"缺少错误码 {code.name} 的默认消息"


class TestBusinessException:
    """业务异常验证。"""

    def test_exception_carries_error_code(self):
        exc = BusinessException(ErrorCode.USER_NOT_FOUND, "用户 123 不存在")
        assert exc.error_code == ErrorCode.USER_NOT_FOUND
        assert exc.status_code == 404
        assert exc.detail == "用户 123 不存在"

    def test_exception_uses_default_message_when_no_detail(self):
        exc = BusinessException(ErrorCode.INVALID_PARAMS)
        assert exc.detail == ErrorCode.INVALID_PARAMS.name

    def test_exception_status_code_matches_error_code(self):
        for code in ErrorCode:
            exc = BusinessException(code)
            assert exc.status_code == code // 100


class TestRequestIdMiddleware:
    """请求追踪中间件验证。"""

    @pytest.fixture
    def test_app(self):
        app = FastAPI()
        register_middleware(app)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        return app

    def test_generates_request_id_when_absent(self, test_app):
        with TestClient(test_app) as client:
            response = client.get("/test")
            assert REQUEST_ID_HEADER in response.headers
            assert response.headers[REQUEST_ID_HEADER]  # 非空

    def test_passthrough_client_request_id(self, test_app):
        with TestClient(test_app) as client:
            custom_id = "my-custom-id-12345"
            response = client.get("/test", headers={REQUEST_ID_HEADER: custom_id})
            assert response.headers[REQUEST_ID_HEADER] == custom_id

    def test_security_headers_present(self, test_app):
        with TestClient(test_app) as client:
            response = client.get("/test")
            assert response.headers.get("X-Content-Type-Options") == "nosniff"
            assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"

    def test_request_id_is_uuid_format_when_generated(self, test_app):
        import uuid as uuid_mod

        with TestClient(test_app) as client:
            response = client.get("/test")
            request_id = response.headers[REQUEST_ID_HEADER]
            # 应能解析为 UUID
            parsed = uuid_mod.UUID(request_id)
            assert str(parsed) == request_id
