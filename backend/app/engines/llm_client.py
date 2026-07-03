"""
LLM 客户端引擎 — 统一封装大模型调用。

架构原则：
    - 所有 LLM 调用通过此模块，不散落在路由/服务中
    - 无 API Key 时自动降级为规则逻辑（fallback），不报错
    - 支持 OpenAI 兼容接口（DeepSeek / Qwen / OpenAI 均可）
    - embedding 调用与 chat 调用分离，便于独立缓存
"""
import json
import logging
from typing import Any

from openai import OpenAI

from app.config import settings

logger = logging.getLogger("app.engines.llm_client")


class LLMClient:
    """LLM 统一客户端。无 API Key 时所有方法返回 None（降级模式）。"""

    def __init__(self) -> None:
        self._client: OpenAI | None = None
        if settings.LLM_ENABLED and settings.LLM_API_KEY:
            try:
                self._client = OpenAI(
                    api_key=settings.LLM_API_KEY,
                    base_url=settings.LLM_BASE_URL,
                )
                logger.info("LLM 客户端已初始化: model=%s, base_url=%s",
                            settings.LLM_MODEL, settings.LLM_BASE_URL)
            except Exception as e:
                logger.warning("LLM 客户端初始化失败，降级为规则模式: %s", e)
        else:
            logger.info("LLM 未启用（LLM_ENABLED=false 或无 API_KEY），使用规则模式")

    @property
    def available(self) -> bool:
        """LLM 是否可用（已配置且初始化成功）。"""
        return self._client is not None

    # ===== Chat 对话 =====

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str | None:
        """调用 LLM 对话接口，返回文本。失败时返回 None。

        Args:
            messages: OpenAI 格式的消息列表
            temperature: 采样温度，None 时使用全局默认
            max_tokens: 最大输出 token 数

        Returns:
            LLM 生成的文本，或 None（降级/失败时）
        """
        if not self.available:
            return None

        try:
            resp = self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=temperature or settings.LLM_TEMPERATURE,
                max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
            )
            content = resp.choices[0].message.content
            # 记录 token 使用量
            if resp.usage:
                logger.debug("LLM 调用: input=%d tokens, output=%d tokens",
                             resp.usage.prompt_tokens, resp.usage.completion_tokens)
            return content
        except Exception as e:
            logger.warning("LLM chat 调用失败: %s", e)
            return None

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> dict | None:
        """调用 LLM 并解析 JSON 输出。

        在 prompt 中要求 LLM 返回纯 JSON，此方法负责解析。
        解析失败时返回 None。
        """
        raw = self.chat(messages, temperature=temperature, max_tokens=settings.LLM_MAX_TOKENS)
        if not raw:
            return None
        # 尝试提取 JSON（LLM 可能包裹 ```json ... ``` 标记）
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        raw = raw.strip()

        # 尝试直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 尝试提取第一个 { ... } 块（LLM 可能在 JSON 前后加了文字）
        import re
        json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if not json_match:
            # 尝试匹配嵌套 JSON
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # 尝试修复常见 JSON 格式错误（缺少逗号、引号等）
        fixed = raw
        # 修复 "key": "value" "key2" 之间缺少逗号
        fixed = re.sub(r'"\s+"\s*"', '", "', fixed)
        # 修复 } { 之间缺少逗号
        fixed = re.sub(r'\}\s*\{', '}, {', fixed)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            logger.warning("LLM 返回内容无法解析为 JSON: %s", raw[:200])
            return None

    # ===== Embedding 向量 =====

    def embed(self, text: str) -> list[float] | None:
        """获取文本的 embedding 向量。

        Returns:
            float 列表，或 None（降级/失败时）
        """
        if not self.available:
            return None
        try:
            resp = self._client.embeddings.create(
                model=settings.LLM_EMBEDDING_MODEL,
                input=text,
            )
            return resp.data[0].embedding
        except Exception as e:
            logger.warning("LLM embedding 调用失败: %s", e)
            return None

    def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """批量获取 embedding 向量。

        Returns:
            与 texts 等长的列表，每个元素为向量或 None
        """
        if not self.available:
            return [None] * len(texts)
        try:
            resp = self._client.embeddings.create(
                model=settings.LLM_EMBEDDING_MODEL,
                input=texts,
            )
            # 按 index 排序确保顺序正确
            sorted_data = sorted(resp.data, key=lambda x: x.index)
            return [d.embedding for d in sorted_data]
        except Exception as e:
            logger.warning("LLM batch embedding 调用失败: %s", e)
            return [None] * len(texts)


# 全局单例
llm_client = LLMClient()
