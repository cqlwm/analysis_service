from g4f.client import Client
models = [
    "glm-4.7-thinking",
]
client = Client()
response = client.chat.completions.create(
    model="glm-5:free",
    messages=[
        {"role": "user", "content": "Hello!"}
    ],
)
print(response.choices[0].message.content)

if __name__ == "__main__":
    pass
