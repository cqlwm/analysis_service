from .config import get_config
from .clients import OpenAICompatibleClient, ApiType


class LLMClientFactory:
    _clients = {}

    @classmethod
    def get_client(cls, provider_name: str, model: str) -> OpenAICompatibleClient:
        config = get_config()
        api_type = config.get_provider_api_type(provider_name)
        cache_key = f"{provider_name}:{model}:{api_type}"

        if cache_key in cls._clients:
            return cls._clients[cache_key]

        provider_config = config.get_provider(provider_name)

        if not provider_config:
            raise ValueError(f"Provider '{provider_name}' not found in config")

        client = OpenAICompatibleClient(
            api_key=provider_config.get("api_key", ""),
            base_url=provider_config.get("base_url", ""),
            model=model,
            api_type=api_type
        )

        cls._clients[cache_key] = client
        return client

    @classmethod
    def clear_cache(cls):
        cls._clients.clear()
