from __future__ import annotations
from typing import List, Dict, Generator, Optional
import os
from openai import OpenAI
from config import settings

class LLMClient:
    """Handles communication with LLM providers (OpenAI, Gemini, Ollama, DeepSeek, vLLM)."""

    def __init__(self):
        self._client: Optional[OpenAI] = None
        self._cooldown_until: float = 0.0
        self.reload()

    def reload(self) -> None:
        settings.reload()
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_BASE_URL
        self.model = settings.LLM_MODEL
        self._cooldown_until = 0.0
        self._init_client()

    def _init_client(self) -> None:
        if self.api_key and self.api_key.strip():
            self._client = OpenAI(
                api_key=self.api_key.strip(),
                base_url=self.base_url.strip() if self.base_url else None,
            )
        else:
            self._client = None

    def update_credentials(self, api_key: str, base_url: Optional[str] = None, model: Optional[str] = None) -> None:
        """Dynamically update LLM credentials at runtime."""
        self.api_key = api_key
        if base_url:
            self.base_url = base_url
        if model:
            self.model = model
        self._cooldown_until = 0.0
        self._init_client()

    def is_configured(self) -> bool:
        """Checks if a valid LLM API key has been configured and is not currently in quota cooldown."""
        import time
        if not self._client and settings.LLM_API_KEY:
            self.reload()
        if not self._client:
            return False
        return time.time() >= self._cooldown_until

    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
        """Synchronously calls the LLM and returns the text response."""
        import time
        if not self._client:
            raise RuntimeError(
                "LLM API Key is not configured. Please set LLM_API_KEY in your .env file or call /api/config/llm"
            )
        if time.time() < self._cooldown_until:
            raise RuntimeError("LLM is temporarily cooling down due to previous quota limit.")

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            err_msg = str(e).lower()
            if "insufficient_quota" in err_msg or "429" in err_msg or "quota" in err_msg:
                self._cooldown_until = time.time() + 120.0
                print("[LLMClient] Quota exhausted (429). Activating 120s cooldown so queries respond instantly via heuristics.")
            raise e

    def chat_stream(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> Generator[str, None, None]:
        """Streams the LLM tokens as a generator."""
        if not self._client:
            raise RuntimeError("LLM API Key is not configured.")

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

llm_client = LLMClient()
