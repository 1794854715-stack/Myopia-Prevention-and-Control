import os
import time
import random
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tqdm import tqdm
import chardet


class PeopleMyopiaScraper:
    def __init__(self):
        self.base_url = "http://www.people.com.cn"
        self.search_url = "http://search.people.cn/getNewsResult/"
        self.data = []

        # 本地User-Agent列表
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        ]

        # Chrome配置（保持不变）
        self.chrome_options = Options()
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")

        # 随机等待时间（保持不变）
        self.min_wait = 3
        self.max_wait = 8

        # 使用chromedriver（保持不变）
        self.service = Service(executable_path="chromedriver.exe")

    def random_wait(self):
        """随机等待时间"""
        time.sleep(random.uniform(self.min_wait, self.max_wait))

    def get_random_user_agent(self):
        """获取随机User-Agent"""
        return random.choice(self.user_agents)

    def detect_encoding(self, response):
        """自动检测网页编码"""
        encoding = chardet.detect(response.content)['encoding']
        return 'gbk' if encoding and encoding.lower() in ('gb2312', 'gbk') else 'utf-8'

    def search_articles(self, keyword="近视", pages=6):
        """搜索文章（修改为新的搜索接口）"""
        driver = webdriver.Chrome(service=self.service, options=self.chrome_options)

        try:
            for page in range(1, pages + 1):
                # 修改为新的URL格式，添加必要的查询参数
                url = f"{self.search_url}?channel=kpzg&x=0&y=0&keyword={keyword}&page={page}"
                print(f"正在抓取第 {page} 页: {url}")

                driver.get(url)
                self.random_wait()

                # 更新User-Agent
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": self.get_random_user_agent()
                })

                # 更宽松的等待条件（可能需要根据新页面结构调整）
                try:
                    WebDriverWait(driver, 20).until(
                        EC.or_(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".result-item")),
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".search-item")),
                            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.people.com.cn']")),
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".search-list"))
                        )
                    )
                except Exception as e:
                    print(f"第 {page} 页等待超时，尝试继续解析...")
                    # 即使超时也尝试解析已有内容

                # 解析页面
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')

                # 更灵活的文章条目选择（可能需要根据新页面结构调整）
                items = []
                for selector in ['.result-item', '.search-item', 'a[href*=".people.com.cn"]']:
                    items = soup.select(selector)
                    if items:
                        break

                if not items:
                    print(f"第 {page} 页未找到文章条目")
                    continue

                for item in items:
                    try:
                        title = item.get_text(" ", strip=True)
                        title = ' '.join(title.split())

                        # 跳过非目标文章
                        if not any(k in title for k in ["近视", "视力", "眼镜", "眼科"]):
                            continue

                        link = item.get('href', '')
                        if not link.startswith('http'):
                            link = urljoin(self.base_url, link)

                        # 提取发布时间（可能需要根据新页面结构调整）
                        pub_time = ""
                        time_tag = item.find_parent().find(class_=lambda x: x and ('date' in x or 'time' in x))
                        if time_tag:
                            pub_time = time_tag.get_text(strip=True)

                        self.data.append({
                            'title': title,
                            'url': link,
                            'source': '人民网',
                            'publish_time': pub_time,
                            'content': ''
                        })

                    except Exception as e:
                        print(f"提取文章信息出错: {str(e)}")
                        continue

                print(f"第 {page} 页获取 {len(items)} 篇文章")
                self.random_wait()

        except Exception as e:
            print(f"搜索过程中发生错误: {str(e)}")
        finally:
            driver.quit()

    # 以下方法保持不变
    def get_article_details(self):
        """获取文章详情（混合模式）"""
        if not self.data:
            print("没有可处理的文章数据")
            return

        driver = webdriver.Chrome(service=self.service, options=self.chrome_options)

        try:
            for article in tqdm(self.data, desc="获取文章详情"):
                try:
                    # 优先使用requests（更快）
                    headers = {'User-Agent': self.get_random_user_agent()}
                    response = requests.get(article['url'], headers=headers, timeout=15)
                    response.encoding = self.detect_encoding(response)

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        content = self._extract_content(soup)
                        if content:
                            article['content'] = content
                            continue

                    # requests失败时使用selenium
                    driver.get(article['url'])
                    # 更新User-Agent
                    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                        "userAgent": self.get_random_user_agent()
                    })

                    # 更宽松的等待条件
                    WebDriverWait(driver, 15).until(
                        EC.or_(
                            EC.presence_of_element_located((By.TAG_NAME, 'article')),
                            EC.presence_of_element_located((By.CSS_SELECTOR, '.content')),
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
                        )
                    )
                    html = driver.page_source
                    soup = BeautifulSoup(html, 'html.parser')
                    article['content'] = self._extract_content(soup)

                    self.random_wait()

                except Exception as e:
                    print(f"获取 {article['title']} 详情失败: {str(e)}")
                    continue

        finally:
            driver.quit()

    def _extract_content(self, soup):
        """多模式匹配正文内容"""
        for selector in [
            '.rm_txt_con',
            '.article-content',
            '.content',
            'div[class*="text"]',
            'div[class*="content"]',
            'div[style*="font-size"]',
            'article'
        ]:
            content = soup.select_one(selector)
            if content:
                # 清理无用元素
                for elem in content.select("script, style, iframe, noscript, .ad"):
                    elem.decompose()
                text = content.get_text('\n', strip=True)
                # 简单清理空白行
                return '\n'.join([line.strip() for line in text.split('\n') if line.strip()])
        return ""

    def save_to_json(self, filename="myopia_articles.json"):
        """保存结果"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f"已保存 {len(self.data)} 篇文章到 {filename}")


if __name__ == "__main__":
    scraper = PeopleMyopiaScraper()

    print("开始搜索文章...")
    scraper.search_articles(pages=6)

    if scraper.data:
        print("\n开始获取文章详情...")
        scraper.get_article_details()

        print("\n保存结果...")
        scraper.save_to_json()
    else:
        print("未获取到文章数据")