import time

import openai
import os
import logging
from openai.types.chat.chat_completion_system_message_param import ChatCompletionSystemMessageParam
from openai.types.chat.chat_completion_user_message_param import ChatCompletionUserMessageParam
from openai.types.chat.chat_completion_assistant_message_param import ChatCompletionAssistantMessageParam
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
import dotenv

dotenv.load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_API_BASE_URL", "https://api.siliconflow.cn/v1")
model_name = os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3.2")
min_model_name = os.getenv("MIN_MODEL_NAME", "Qwen/Qwen3-8B")

if not api_key:
    raise ValueError("OPENAI_API_KEY not set")

client = openai.OpenAI(api_key=api_key, base_url=base_url)

messages: list[ChatCompletionMessageParam] = [
    ChatCompletionUserMessageParam(content="如何把大象装进冰箱里？", role="user"),
]

response = client.chat.completions.create(
    model=min_model_name,
    messages=messages,
    max_tokens=2000,
    extra_body={
        'thinking': {
            "type": "enabled"
        },
        "caching":{"type":"enabled"},
        "expire_at": int(time.time()) + 3000
    },
)

print(response.choices[0].message.content)

if __name__ == "__main__":
    pass


