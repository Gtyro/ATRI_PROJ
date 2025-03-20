from openai import OpenAI
client = OpenAI(api_key="<your key>", base_url="https://api.deepseek.com")

# Round 1
messages = [
    {"role": "system", "content": "你是一个AI助手，擅长回答关于地理和自然的问题。"},
    {"role": "user", "content": "世界上最高的山是哪座？"}]
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages
)

messages.append(response.choices[0].message)
print(f"Messages Round 1: {messages}")

# Round 2
messages.append({"role": "user", "content": "世界上第二高的山是哪座？"})
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages
)

messages.append(response.choices[0].message)
print(f"Messages Round 2: {messages}")