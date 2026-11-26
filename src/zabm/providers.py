from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Protocol, TypeGuard, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from zabm.response import ProviderIdentity

logger = logging.getLogger("zabm.llm")

PROVIDER_NAMES: Final[tuple[str, ...]] = (
    "deterministic",
    "openai-compatible",
    "openai",
    "deepseek",
)
MAX_COMPLETION_TOKENS: Final = 1024


class ProviderError(RuntimeError):
    pass


def normalize_json_content(content: str) -> str:
    lines = content.strip().splitlines()
    if (
        len(lines) >= 2
        and lines[0].strip().lower() in {"```", "```json"}
        and lines[-1].strip() == "```"
    ):
        return "\n".join(lines[1:-1]).strip()
    return content


class ModelProvider(Protocol):
    identity: ProviderIdentity

    @property
    def seed_supported(self) -> bool: ...

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        seed: int = 0,
    ) -> str: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        embedding_model: str,
        embedding_base_url: str | None = None,
        embedding_api_key: str | None = None,
        configuration: str,
        api_key: str | None = None,
        timeout: float = 60.0,
        provider_name: str = "openai-compatible",
        supports_seed: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._embedding_base_url = (embedding_base_url or base_url).rstrip("/")
        self._embedding_api_key = embedding_api_key if embedding_base_url is not None else api_key
        self._timeout = timeout
        self._supports_seed = supports_seed
        self.identity = ProviderIdentity(
            provider=provider_name,
            model=model,
            embedding_model=embedding_model,
            configuration=configuration,
        )

    @property
    def seed_supported(self) -> bool:
        return self._supports_seed

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        seed: int = 0,
    ) -> str:
        request_payload: dict[str, Any] = {
            "model": self.identity.model,
            "messages": list(messages),
            "temperature": 0,
            "max_tokens": MAX_COMPLETION_TOKENS,
        }
        if self.seed_supported:
            request_payload["seed"] = seed
        logger.debug(
            "request provider=%s model=%s seed=%s messages=%s",
            self.identity.provider,
            self.identity.model,
            seed if self.seed_supported else "not-supported",
            json.dumps(list(messages), ensure_ascii=False),
        )
        payload = self._post("/chat/completions", request_payload)
        try:
            choices = payload["choices"]
            content = choices[0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("provider returned an invalid chat completion") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("provider returned an empty chat completion")
        logger.debug(
            "response provider=%s model=%s content=%s",
            self.identity.provider,
            self.identity.model,
            content,
        )
        return content

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if self.identity.embedding_model == "not-configured":
            raise ProviderError(f"{self.identity.provider} does not configure an embedding model")
        logger.debug(
            "embedding-request provider=%s model=%s input_count=%d",
            self.identity.provider,
            self.identity.embedding_model,
            len(texts),
        )
        payload = self._post(
            "/embeddings",
            {
                "model": self.identity.embedding_model,
                "input": list(texts),
            },
            base_url=self._embedding_base_url,
            api_key=self._embedding_api_key,
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
        if len(vectors) != len(texts):
            raise ProviderError(
                f"provider returned {len(vectors)} embeddings for {len(texts)} inputs"
            )
        if any(not vector for vector in vectors):
            raise ProviderError("provider returned an empty embedding vector")
        logger.debug(
            "embedding-response provider=%s model=%s vector_count=%d dimensions=%d",
            self.identity.provider,
            self.identity.embedding_model,
            len(vectors),
            len(vectors[0]) if vectors else 0,
        )
        return vectors

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        effective_api_key = api_key if base_url is not None else self._api_key
        if effective_api_key:
            headers["Authorization"] = f"Bearer {effective_api_key}"
        request = Request(
            f"{base_url or self._base_url}{path}",
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


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    base_url: str | None
    base_url_env: str
    model: str | None
    model_env: str
    embedding_model: str | None
    embedding_model_env: str
    api_key_env: str | None
    api_key_required: bool
    supports_seed: bool


PROVIDER_PROFILES: Final[dict[str, ProviderProfile]] = {
    "openai-compatible": ProviderProfile(
        name="openai-compatible",
        base_url=None,
        base_url_env="ZABM_PROVIDER_URL",
        model=None,
        model_env="ZABM_MODEL",
        embedding_model=None,
        embedding_model_env="ZABM_EMBEDDING_MODEL",
        api_key_env=None,
        api_key_required=False,
        supports_seed=True,
    ),
    "openai": ProviderProfile(
        name="openai",
        base_url="https://api.openai.com/v1",
        base_url_env="OPENAI_BASE_URL",
        model=None,
        model_env="OPENAI_MODEL",
        embedding_model="text-embedding-3-small",
        embedding_model_env="OPENAI_EMBEDDING_MODEL",
        api_key_env="OPENAI_API_KEY",
        api_key_required=True,
        supports_seed=True,
    ),
    "deepseek": ProviderProfile(
        name="deepseek",
        base_url="https://api.deepseek.com",
        base_url_env="DEEPSEEK_BASE_URL",
        model="deepseek-flash",
        model_env="DEEPSEEK_MODEL",
        embedding_model="not-configured",
        embedding_model_env="DEEPSEEK_EMBEDDING_MODEL",
        api_key_env="DEEPSEEK_API_KEY",
        api_key_required=True,
        supports_seed=False,
    ),
}


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
    profile = PROVIDER_PROFILES.get(provider)
    if profile is None:
        raise ProviderError(
            f"unsupported provider: {provider}; choose from {', '.join(PROVIDER_NAMES)}"
        )
    effective_base_url = (
        base_url
        or _environment_value("ZABM_PROVIDER_URL", profile.base_url_env)
        or profile.base_url
    )
    effective_model = model or _environment_value("ZABM_MODEL", profile.model_env) or profile.model
    effective_embedding_model = (
        embedding_model
        or _environment_value(
            "ZABM_EMBEDDING_MODEL",
            profile.embedding_model_env,
        )
        or profile.embedding_model
    )
    embedding_base_url = _environment_value("ZABM_EMBEDDING_PROVIDER_URL")
    if not effective_base_url:
        raise ProviderError(f"--provider-url or {profile.base_url_env} is required")
    if not effective_model:
        raise ProviderError(f"--model or {profile.model_env} is required for {profile.name}")
    if not effective_embedding_model:
        raise ProviderError(
            f"--embedding-model or {profile.embedding_model_env} is required for {profile.name}"
        )
    api_key = _environment_value("ZABM_PROVIDER_API_KEY", profile.api_key_env)
    if profile.api_key_required and not api_key:
        assert profile.api_key_env is not None
        raise ProviderError(f"{profile.api_key_env} is required for {profile.name}")
    default_configuration = (
        f"temperature=0,seed=0,max_tokens={MAX_COMPLETION_TOKENS}"
        if profile.name == "openai-compatible"
        else (
            f"{profile.name}:temperature=0"
            + (",seed=0" if profile.supports_seed else "")
            + f",max_tokens={MAX_COMPLETION_TOKENS}"
        )
    )
    return OpenAICompatibleProvider(
        base_url=effective_base_url,
        model=effective_model,
        embedding_model=effective_embedding_model,
        embedding_base_url=embedding_base_url,
        embedding_api_key=(
            _environment_value("ZABM_EMBEDDING_PROVIDER_API_KEY")
            if embedding_base_url is not None
            else None
        ),
        configuration=configuration or default_configuration,
        api_key=api_key,
        provider_name=profile.name,
        supports_seed=profile.supports_seed,
    )


def _environment_value(*names: str | None) -> str | None:
    for name in names:
        if name is None:
            continue
        value = os.getenv(name)
        if value:
            return value
    return None


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, int | float)
