import os
from openai import OpenAI
import dotenv
from openai.types.responses import ResponseInputTextParam
from openai.types.responses.response_input_param import Message

dotenv.load_dotenv()
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

if __name__ == "__main__":
    pass