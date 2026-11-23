from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any, Protocol, TypeGuard, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from zabm.response import ProviderIdentity


class ProviderError(RuntimeError):
    pass


class ModelProvider(Protocol):
    identity: ProviderIdentity

    def complete(self, messages: Sequence[dict[str, str]]) -> str: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        embedding_model: str,
        configuration: str,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self.identity = ProviderIdentity(
            provider="openai-compatible",
            model=model,
            embedding_model=embedding_model,
            configuration=configuration,
        )

    def complete(self, messages: Sequence[dict[str, str]]) -> str:
        payload = self._post(
            "/chat/completions",
            {
                "model": self.identity.model,
                "messages": list(messages),
                "temperature": 0,
                "seed": 0,
            },
        )
        try:
            choices = payload["choices"]
            content = choices[0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("provider returned an invalid chat completion") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("provider returned an empty chat completion")
        return content

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        payload = self._post(
            "/embeddings",
            {
                "model": self.identity.embedding_model,
                "input": list(texts),
            },
        )
        try:
            rows = payload["data"]
        except (KeyError, TypeError) as exc:
            raise ProviderError("provider returned an invalid embedding response") from exc
        if not isinstance(rows, list):
            raise ProviderError("provider returned non-numeric embeddings")
        vectors: list[list[float]] = []
        for row_value in cast(list[object], rows):
            if not isinstance(row_value, dict):
                raise ProviderError("provider returned non-numeric embeddings")
            row = cast(dict[str, object], row_value)
            vector = row.get("embedding")
            if not isinstance(vector, list):
                raise ProviderError("provider returned non-numeric embeddings")
            vector_values = cast(list[object], vector)
            if not all(_is_number(value) for value in vector_values):
                raise ProviderError("provider returned non-numeric embeddings")
            numeric_vector = cast(list[int | float], vector_values)
            vectors.append([float(value) for value in numeric_vector])
        return vectors

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = Request(
            f"{self._base_url}{path}",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                result: object = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise ProviderError(f"provider request failed: {exc}") from exc
        if not isinstance(result, dict):
            raise ProviderError("provider returned a non-object response")
        return cast(dict[str, Any], result)


def configured_provider(
    *,
    provider: str | None,
    base_url: str | None,
    model: str | None,
    embedding_model: str | None,
    configuration: str | None,
) -> ModelProvider | None:
    provider = provider or (
        "openai-compatible"
        if base_url or model or embedding_model or configuration
        else "deterministic"
    )
    if provider == "deterministic":
        return None
    if provider != "openai-compatible":
        raise ProviderError(f"unsupported provider: {provider}")
    if not base_url:
        raise ProviderError("--provider-url is required for an openai-compatible provider")
    if not model:
        raise ProviderError("--model is required for an openai-compatible provider")
    if not embedding_model:
        raise ProviderError("--embedding-model is required for an openai-compatible provider")
    return OpenAICompatibleProvider(
        base_url=base_url,
        model=model,
        embedding_model=embedding_model,
        configuration=configuration or "temperature=0,seed=0",
        api_key=os.getenv("ZABM_PROVIDER_API_KEY"),
    )


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, int | float)
