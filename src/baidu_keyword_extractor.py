import requests
import json
import time
import os
import hashlib
from typing import List, Dict, Optional
from pathlib import Path


class BaiduKeywordExtractor:
    def __init__(self, api_key: str, secret_key: str):
        """
        初始化关键词提取器（纯百度API版本）

        :param api_key: 百度API Key
        :param secret_key: 百度Secret Key
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = None
        self.token_expire_time = 0
        self.total_requests = 0
        self.service_available = False

        # API配置
        self.auth_url = "https://aip.baidubce.com/oauth/2.0/token"
        self.keyword_url = "https://aip.baidubce.com/rpc/2.0/nlp/v1/txt_keywords_extraction"
        self.timeout = 15

        self._init_service()

    def _init_service(self):
        """初始化服务连接"""
        print("\n=== 初始化百度关键词提取服务 ===")
        self.access_token = self._get_access_token()
        self.service_available = bool(self.access_token)

    def _get_access_token(self) -> Optional[str]:
        """获取百度API访问令牌（带缓存）"""
        if self.access_token and time.time() < self.token_expire_time:
            return self.access_token

        print("🔄 正在获取Access Token...")
        try:
            response = requests.post(
                self.auth_url,
                params={
                    "grant_type": "client_credentials",
                    "client_id": self.api_key,
                    "client_secret": self.secret_key
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            if "access_token" in data:
                self.access_token = data["access_token"]
                self.token_expire_time = time.time() + data.get("expires_in", 2592000) - 300  # 提前5分钟过期
                print(
                    f"✅ 获取Token成功 (有效期至: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.token_expire_time))}")
                return self.access_token

            print(f"❌ 获取Token失败: {data.get('error_description', '未知错误')}")
        except Exception as e:
            print(f"❌ 获取Token异常: {str(e)}")
        return None

    def _preprocess_text(self, text: str) -> str:
        """文本预处理"""
        import re
        # 移除特殊字符但保留中文标点
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。？！、；：“”‘’（）【】…\- \n]', '', text)
        # 合并空白字符
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:2000]  # 百度API限制

    def extract_unique_keywords(self, original_list):
        seen_words = {}
        result_list = []

        for item in original_list:
            word = item["word"]
            if word not in seen_words:
                seen_words[word] = 1
                result_list.append(item)

        return result_list


    def extract_keywords(self, text: str, num: int = 5, retry: int = 0) -> List[Dict]:
        """
        提取关键词（纯百度API版本）

        :param text: 待处理文本
        :param num: 返回关键词数量
        :param retry: 当前重试次数（内部使用）
        :return: [{"word": str, "score": float}]
        :raises: Exception 当API调用失败时抛出
        """
        if not self.access_token:
            raise ValueError("Access Token不可用")

        if not text.strip():
            return []

        payload = {
            "text": [self._preprocess_text(text)],
            "top_num": num  # 官方文档要求的参数名
        }

        print(f"\n=== 百度API请求 ===")
        print(f"文本长度: {len(payload['text'])}")
        print(f"参数: {json.dumps(payload, ensure_ascii=False, indent=2)}")

        try:
            start_time = time.time()
            response = requests.post(
                f"{self.keyword_url}?access_token={self.access_token}",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                timeout=self.timeout
            )
            self.total_requests += 1

            print(f"⏱️ 请求耗时: {(time.time() - start_time):.2f}s")
            print(f"状态码: {response.status_code}")

            response.raise_for_status()
            result = response.json()

            print("=== 原始响应 ===")

            if "error_code" in result:
                error_msg = f"百度API错误: {result['error_msg']} (code: {result['error_code']})"

                # Token过期处理
                if result["error_code"] == 110 and retry < 2:
                    print("🔄 Token已过期，尝试刷新...")
                    self.access_token = self._get_access_token()
                    if self.access_token:
                        return self.extract_keywords(text, num, retry + 1)

                # QPS限制处理
                elif result["error_code"] == 18 and retry < 3:
                    wait_time = 2 ** retry
                    print(f"⚠️ 触发限流，等待 {wait_time}s 后重试...")
                    time.sleep(wait_time)
                    return self.extract_keywords(text, num, retry + 1)

                raise ValueError(error_msg)

            # 调用函数提取唯一的词汇列表
            print("--", type(result))
            # return result.get("items", [])
            return result.get("results", [])

        except requests.exceptions.RequestException as e:
            print(f"❌ 网络请求异常: {str(e)}")
            if retry < 3:
                print(f"🔄 第 {retry + 1} 次重试...")
                time.sleep(1)
                return self.extract_keywords(text, num, retry + 1)
            raise

    def process_articles(self, input_path: str, output_path: str):
        """
        处理所有文章

        :param input_path: 输入JSON文件路径
        :param output_path: 输出JSON文件路径
        """
        print("\n=== 开始处理文章 ===")

        # 验证输入文件
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"❌ 输入文件不存在: {input_path}")

        # 加载数据
        with open(input_path, "r", encoding="utf-8") as f:
            articles = json.load(f)

        if not isinstance(articles, list):
            raise ValueError("❌ 输入文件应该包含JSON数组")

        print(f"📂 找到 {len(articles)} 篇文章")
        results = []
        success_count = 0

        # 处理每篇文章
        for idx, article in enumerate(articles, 1):
            try:
                if not all(k in article for k in ["title", "content"]):
                    raise ValueError("文章缺少title或content字段")

                content = f"{article['title']}\n{article['content']}"
                print(f"\n🔍 处理文章 #{idx}: {article['title'][:30]}...")

                keywords = self.extract_keywords(content)
                # 过滤重复的数据
                keywords = self.extract_unique_keywords(keywords)
                print(f"✅ 提取到 {len(keywords)} 个关键词: {[kw['word'] for kw in keywords]}")

                results.append({
                    "id": article.get("id", hashlib.md5(content.encode()).hexdigest()),
                    "title": article["title"],
                    "source": article.get("source", ""),
                    "url": article.get("url", ""),
                    "keywords": [kw["word"] for kw in keywords],
                    "scores": [kw["score"] for kw in keywords]
                })
                success_count += 1

                # 控制请求频率
                time.sleep(0.5)

            except Exception as e:
                print(f"❌ 处理失败: {str(e)}")
                continue

        # 保存结果
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n=== 处理完成 ===")
        print(f"✅ 成功处理: {success_count}/{len(articles)}")
        print(f"💾 结果保存到: {output_path}")
        print(f"📊 百度API调用次数: {self.total_requests}")


if __name__ == "__main__":
    # 从config.py导入配置
    from config import BAIDU_API

    BAIDU_API_KEY = BAIDU_API.get("api_key")
    BAIDU_SECRET_KEY = BAIDU_API.get("secret_key")
    print("api", BAIDU_API_KEY)
    print("secret_key", BAIDU_SECRET_KEY)

    # 示例用法
    extractor = BaiduKeywordExtractor(
        api_key=BAIDU_API_KEY,
        secret_key=BAIDU_SECRET_KEY
    )

    # # 测试单条文本
    # test_text = "近视防控需要每天户外活动2小时，减少电子屏幕使用时间。最新研究表明，蓝光会加速近视发展。"
    # print("\n=== 测试关键词提取 ===")
    # try:
    #     keywords = extractor.extract_keywords(test_text)
    #     print(f"提取结果: {keywords}")
    # except Exception as e:
    #     print(f"❌ 提取失败: {str(e)}")

    # 处理全部文章（示例路径）
    extractor.process_articles(
        input_path="myopia_articles.json",
        output_path="processed_keywords.json"
    )