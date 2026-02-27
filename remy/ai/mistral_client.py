"""
Mistral AI client for Remy.
"""

import logging
from typing import AsyncIterator

import httpx
from ..config import settings

logger = logging.getLogger(__name__)


class MistralClient:
    """Client for interacting with the Mistral AI API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.mistral_api_key
        self._base_url = "https://api.mistral.ai/v1"

    async def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream a chat completion from Mistral."""
        if not self._api_key:
            logger.warning("Mistral API key not configured")
            yield "⚠️ _Mistral API key not configured._"
            return

        model = model or settings.mistral_model_medium
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream(
                    "POST", f"{self._base_url}/chat/completions", json=payload, headers=headers
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error("Mistral API error (%d): %s", response.status_code, error_text)
                        yield f"⚠️ _Mistral API error ({response.status_code})_"
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            
                            import json
                            try:
                                data = json.loads(data_str)
                                if delta := data["choices"][0].get("delta", {}).get("content"):
                                    yield delta
                            except (json.JSONDecodeError, KeyError, IndexError) as e:
                                logger.debug("Error parsing Mistral stream chunk: %s", e)
            except Exception as e:
                logger.error("Mistral stream failed: %s", e)
                yield f"⚠️ _Mistral connection failed: {e}_"

    async def is_available(self) -> bool:
        """Check if Mistral API is available and key is valid (briefly)."""
        if not self._api_key:
            return False
        # Simple models list check (fast)
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                headers = {"Authorization": f"Bearer {self._api_key}"}
                response = await client.get(f"{self._base_url}/models", headers=headers)
                return response.status_code == 200
            except Exception:
                return False
