from typing import Optional
from .config import get_config
from .factory import LLMClientFactory

MessageList = list[dict[str, str]]


class LLMManager:
    def __init__(self):
        self._config = get_config()

    def chat(
        self,
        model_type: str,
        messages: MessageList,
        max_tokens: int = 2000,
        extra_body: Optional[dict] = None,
        **kwargs
    ) -> str:
        mapping = self._config.get_model_mapping(model_type)
        if not mapping:
            raise ValueError(f"Model type '{model_type}' not found in config")

        provider_name = mapping.get("provider", "")
        model = mapping.get("model", "")

        default_extra_body = self._config.get_model_extra_body(model_type)
        if extra_body:
            default_extra_body.update(extra_body)

        client = LLMClientFactory.get_client(provider_name, model)
        return client.chat(messages, max_tokens, default_extra_body, **kwargs)

    def get_available_model_types(self) -> list:
        return self._config.get_all_model_types()
