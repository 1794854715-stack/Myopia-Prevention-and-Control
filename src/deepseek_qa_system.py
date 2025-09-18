import json
import requests


class DeepSeekChatBot:
    def __init__(self, api_key, model="deepseek-chat", temperature=0.3):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.messages = []
        self.url = "https://api.deepseek.com/chat/completions"
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        self.add_system_message("你是一个近视领域的专家，精通各种近视问题，回答时尽量简洁明了，控制在100字左右。")

    def add_system_message(self, content):
        """添加系统消息"""
        self.messages.append({"role": "system", "content": content})

    def add_message(self, role, content):
        """添加对话消息"""
        self.messages.append({"role": role, "content": content})

    def reset_conversation(self):
        """重置对话历史"""
        self.messages = []
        self.add_system_message("你是一个近视领域的专家，精通各种近视问题，回答时尽量简洁明了，控制在100字左右。")

    def chat(self, user_input, stream=False):
        """执行对话请求"""
        self.add_message("user", user_input)

        data = {
            "model": self.model,
            "messages": self.messages,
            "temperature": self.temperature,
            "max_tokens": 2000,
            "stream": stream
        }

        response = requests.post(
            self.url,
            headers=self.headers,
            json=data,
            stream=stream
        )

        if response.status_code != 200:
            print(f"请求失败，状态码：{response.status_code}")
            print(response.text)
            return None

        assistant_reply = ""

        if stream:
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        json_str = line_str[6:].strip()
                        if json_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(json_str)
                            content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if content:
                                print(content, end='', flush=True)
                                assistant_reply += content
                        except json.JSONDecodeError:
                            print("JSON解析错误")
            print()
        else:
            response_json = response.json()
            assistant_reply = response_json.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(assistant_reply)

        self.add_message("assistant", assistant_reply)
        return assistant_reply



if __name__ == "__main__":
    API_KEY = "sk-390ca58d89df4f7bbffaee0200f8b754"

    bot = DeepSeekChatBot(API_KEY)
    question = "近视原因"
    key = ['近视', '原因']
    # 第一轮对话（非流式）
    keywords_str = '，'.join(key)
    response = bot.chat(question + f"问题关键字：{keywords_str}")
    print("res=", response)
    # 查看完整对话历史
    print("\n完整对话历史：")
    for msg in bot.messages:
        print(f"{msg['role']}: {msg['content'][:50]}...")

