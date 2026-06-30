"""
阶段1 系统测试：API 健康检查与应用启动。

验证 FastAPI 应用能否正常启动并响应请求。
"""
import pytest


@pytest.mark.system
class TestHealthCheck:
    """测试应用健康检查端点。"""

    def test_health_endpoint(self, client):
        """健康检查端点应返回 200 和正确状态。"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_root_endpoint(self, client):
        """根端点应返回前端 HTML 页面。"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "CPA" in response.text

    def test_openapi_docs_available(self, client):
        """OpenAPI 文档应可访问。"""
        response = client.get("/docs")
        assert response.status_code == 200
