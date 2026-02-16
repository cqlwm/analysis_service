import os
import time
import yaml
from pathlib import Path
from typing import Optional, Any
import dotenv

dotenv.load_dotenv()


class LLMConfig:
    _instance = None
    _config: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        config_path = Path(os.getenv("LLM_CONFIG_PATH", "config/llm_providers.yaml"))
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            self._config = yaml.safe_load(f)

        self._resolve_env_vars()

    def _resolve_env_vars(self):
        for provider_name, provider_config in self._config.get("providers", {}).items():
            for key, value in provider_config.items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    provider_config[key] = os.getenv(env_var, "")

    def get_provider(self, name: str) -> dict:
        provider_config = self._config.get("providers", {}).get(name, {}).copy()
        for key, value in provider_config.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                provider_config[key] = os.getenv(env_var, "")
        return provider_config

    def get_provider_api_type(self, name: str) -> str:
        provider = self._config.get("providers", {}).get(name, {})
        return provider.get("api_type", "chat")

    def get_model_mapping(self, model_type: str) -> dict:
        return self._config.get("model_mapping", {}).get(model_type, {})

    def get_model_extra_body(self, model_type: str) -> dict:
        mapping = self._config.get("model_mapping", {}).get(model_type, {})
        extra_body = mapping.get("extra_body", {}).copy()
        self._resolve_time_values(extra_body)
        return extra_body

    def _resolve_time_values(self, obj: Any):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, dict):
                    self._resolve_time_values(value)
                elif isinstance(value, int) and key == "expire_at":
                    if 0 < value < 1000000000:
                        obj[key] = int(time.time()) + value
        elif isinstance(obj, list):
            for item in obj:
                self._resolve_time_values(item)

    def get_all_providers(self) -> dict:
        return self._config.get("providers", {})

    def get_all_model_types(self) -> list:
        return list(self._config.get("model_mapping", {}).keys())


def get_config() -> LLMConfig:
    return LLMConfig()
