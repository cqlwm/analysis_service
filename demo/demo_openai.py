import os
from openai import OpenAI
import dotenv
from openai.types.responses import ResponseInputTextParam
from openai.types.responses.response_input_param import Message
from openai.types.chat.chat_completion_user_message_param import ChatCompletionUserMessageParam

dotenv.load_dotenv()

def ark_demo():
    client = OpenAI(
        base_url='https://ark.cn-beijing.volces.com/api/v3',
        api_key=os.getenv('ARK_API_KEY'),
    )

    response = client.responses.create(
        model="ep-20260216002712-z5fgm",
        input=[Message(content=[ResponseInputTextParam(text="为什么交易中的技术指标具有滞后性", type="input_text")], role='user')],
        extra_body={
            "thinking": {"type": "disabled"},
        }
    )
    print(response.output[0].summary[0].text)
    print(response.output_text)


def aistudio_demo():
    client = OpenAI(
        api_key="36ba812cdae84d32d05e9939d862a09d4831604c",
        base_url="https://api-x3k0h5i9mff2rbr7.aistudio-app.com/v1"
    )
    completion = client.chat.completions.create(
        model="TeichAI/Qwen3-14B-Claude-4.5-Opus-High-Reasoning-Distill-GGUF",
        temperature=0.6,
        messages=[
            ChatCompletionUserMessageParam(content="你使用Claude训练的吗？", role="user")
        ],
        stream=True
    )

    for chunk in completion:
        if hasattr(chunk.choices[0].delta, "reasoning_content") and chunk.choices[0].delta.reasoning_content:
            print(chunk.choices[0].delta.reasoning_content, end="", flush=True)
        else:
            print(chunk.choices[0].delta.content, end="", flush=True)


if __name__ == "__main__":
    aistudio_demo()