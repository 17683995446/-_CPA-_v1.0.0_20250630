"""
LLM 客户端引擎 — 统一封装大模型调用。

架构原则：
    - 所有 LLM 调用通过此模块，不散落在路由/服务中
    - 无 API Key 时自动降级为规则逻辑（fallback），不报错
    - 支持 OpenAI 兼容接口（DeepSeek / Qwen / OpenAI 均可）
    - embedding 调用与 chat 调用分离，便于独立缓存
    - 内置超时、重试、结果缓存机制
"""
import hashlib
import json
import logging
import re
import time
from collections import OrderedDict
from typing import Any

from openai import OpenAI

from app.config import settings

logger = logging.getLogger("app.engines.llm_client")

# LRU 缓存上限
_CACHE_MAX_SIZE = 256
# LRU 缓存默认 TTL（秒）
_CACHE_TTL = 3600


class LRUCache:
    """带 TTL 的 LRU 缓存。"""

    def __init__(self, max_size: int = _CACHE_MAX_SIZE, ttl: int = _CACHE_TTL) -> None:
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        if key not in self._cache:
            return None
        value, ts = self._cache[key]
        if time.time() - ts > self._ttl:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, time.time())
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)


class LLMClient:
    """LLM 统一客户端。无 API Key 时所有方法返回 None（降级模式）。"""

    def __init__(self) -> None:
        self._client: OpenAI | None = None
        self._cache = LRUCache()
        if settings.LLM_ENABLED and settings.LLM_API_KEY:
            try:
                self._client = OpenAI(
                    api_key=settings.LLM_API_KEY,
                    base_url=settings.LLM_BASE_URL,
                    timeout=30.0,        # 30s 超时，防止长请求阻塞
                    max_retries=3,        # SDK 内置重试 3 次
                )
                logger.info("LLM 客户端已初始化: model=%s, base_url=%s, timeout=30s, retries=3",
                            settings.LLM_MODEL, settings.LLM_BASE_URL)
            except Exception as e:
                logger.warning("LLM 客户端初始化失败，降级为规则模式: %s", e)
        else:
            logger.info("LLM 未启用（LLM_ENABLED=false 或无 API_KEY），使用规则模式")

    @property
    def available(self) -> bool:
        """LLM 是否可用（已配置且初始化成功）。"""
        return self._client is not None

    @staticmethod
    def _cache_key(messages: list[dict], **kwargs) -> str:
        """生成缓存键。"""
        raw = json.dumps({"messages": messages, **kwargs}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    # ===== Chat 对话 =====

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        use_cache: bool = True,
    ) -> str | None:
        """调用 LLM 对话接口，返回文本。失败时返回 None。

        Args:
            messages: OpenAI 格式的消息列表
            temperature: 采样温度，None 时使用全局默认
            max_tokens: 最大输出 token 数
            use_cache: 是否使用缓存（默认 True）

        Returns:
            LLM 生成的文本，或 None（降级/失败时）
        """
        if not self.available:
            return None

        temp = temperature or settings.LLM_TEMPERATURE
        tokens = max_tokens or settings.LLM_MAX_TOKENS
        cache_key = self._cache_key(messages, temperature=temp, max_tokens=tokens)

        # 查缓存
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("LLM chat 命中缓存")
                return cached

        try:
            resp = self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=temp,
                max_tokens=tokens,
            )
            content = resp.choices[0].message.content
            # 记录 token 使用量
            if resp.usage:
                logger.debug("LLM 调用: input=%d tokens, output=%d tokens",
                             resp.usage.prompt_tokens, resp.usage.completion_tokens)
            # 写缓存
            if use_cache and content:
                self._cache.set(cache_key, content)
            return content
        except Exception as e:
            logger.warning("LLM chat 调用失败: %s", e)
            return None

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        use_cache: bool = True,
    ) -> dict | None:
        """调用 LLM 并解析 JSON 输出。

        在 prompt 中要求 LLM 返回纯 JSON，此方法负责解析。
        解析失败时返回 None。
        """
        raw = self.chat(messages, temperature=temperature, max_tokens=settings.LLM_MAX_TOKENS, use_cache=use_cache)
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

        # 尝试提取 JSON 块（支持嵌套花括号）
        # 先尝试匹配最外层 { ... }
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # 尝试匹配无嵌套的简单 { ... }
        json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

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
