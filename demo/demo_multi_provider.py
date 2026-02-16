from llm import LLMManager

llm = LLMManager()

messages = [
    {"content": "如何把大象装进冰箱里？", "role": "user"}
]

# print("=== Chat Model (使用默认 extra_body) ===")
# result = llm.chat(model_type="chat_model", messages=messages)
# print(result)
#
# print("\n=== Reasoner Model (使用默认 extra_body) ===")
# result = llm.chat(model_type="reasoner_model", messages=messages)
# print(result)

if __name__ == "__main__":
    r = llm.chat(model_type="reasoner_model", messages=messages)
    print(r)
