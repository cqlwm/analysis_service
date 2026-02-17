import logging
from typing import Optional, Literal
import openai
from openai.types.chat.chat_completion_system_message_param import ChatCompletionSystemMessageParam
from openai.types.chat.chat_completion_user_message_param import ChatCompletionUserMessageParam
from openai.types.chat.chat_completion_assistant_message_param import ChatCompletionAssistantMessageParam
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from openai.types.responses import EasyInputMessageParam

logger = logging.getLogger(__name__)

ApiType = Literal["chat", "responses"]
MessageList = list[dict[str, str]]


class BaseLLMClient:
    def __init__(self, api_key: str, base_url: str, model: str, api_type: ApiType = "chat"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.api_type = api_type
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)

    def chat(
        self,
        messages: MessageList,
        max_tokens: int = 2000,
        extra_body: Optional[dict] = None,
        **kwargs
    ) -> str:
        if not self.api_key:
            raise ValueError(f"API key not set for provider")

        if self.api_type == "responses":
            return self._responses_create(messages, max_tokens, extra_body, **kwargs)
        else:
            return self._chat_create(messages, max_tokens, extra_body, **kwargs)

    def _chat_create(
        self,
        messages: MessageList,
        max_tokens: int = 2000,
        extra_body: Optional[dict] = None,
        **kwargs
    ) -> str:
        chat_messages: list[ChatCompletionMessageParam] = []
        for message in messages:
            if message["role"] == "system":
                chat_messages.append(ChatCompletionSystemMessageParam(content=message["content"], role="system"))
            elif message["role"] == "user":
                chat_messages.append(ChatCompletionUserMessageParam(content=message["content"], role="user"))
            elif message["role"] == "assistant":
                chat_messages.append(ChatCompletionAssistantMessageParam(content=message["content"], role="assistant"))
        response = self._client.chat.completions.create(
            model=self.model,
            messages=chat_messages,
            max_tokens=max_tokens,
            extra_body=extra_body or {},
            **kwargs
        )
        return response.choices[0].message.content or ""

    def _responses_create(
        self,
        messages: MessageList,
        max_tokens: int = 2000,
        extra_body: Optional[dict] = None,
        **kwargs
    ) -> str:
        chat_messages: list[EasyInputMessageParam] = []
        for message in messages:
            role: Literal["user", "assistant", "system", "developer"] = 'user'
            if message["role"] == "system":
                role = "system"
            elif message["role"] == "user":
                role = "user"
            elif message["role"] == "assistant":
                role = "assistant"
            elif message["role"] == "developer":
                role = "developer"

            chat_messages.append(EasyInputMessageParam(content=message["content"], role=role))

        response = self._client.responses.create(
            model=self.model,
            input=chat_messages,
            max_output_tokens=max_tokens,
            extra_body=extra_body or {},
            **kwargs
        )
        # reasoning = response.output[0].summary[0].text
        return response.output_text or ""


class OpenAICompatibleClient(BaseLLMClient):
    pass
