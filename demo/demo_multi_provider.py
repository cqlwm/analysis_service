from llm import LLMManager

llm = LLMManager()

messages = [
    {"content": "如何把大象装进冰箱里？", "role": "user"}
]

print("=== Chat Model (使用默认 extra_body) ===")
result = llm.chat("chat_model", messages)
print(result)

print("\n=== Reasoner Model (使用默认 extra_body) ===")
result = llm.chat("reasoner_model", messages)
print(result)

print("\n=== Mini Model (无默认 extra_body) ===")
result = llm.chat("mini_model", messages)
print(result)

print("\n=== Chat Model (覆盖默认 extra_body) ===")
result = llm.chat("chat_model", messages, extra_body={"temperature": 0.9})
print(result)
