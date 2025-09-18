from baidu_keyword_extractor import BaiduKeywordExtractor
import os


def main():
    print("=== 近视防控文章关键词提取 ===")
    print(f"工作目录: {os.getcwd()}")
    print(f"目录内容: {os.listdir()}")

    try:
        extractor = BaiduKeywordExtractor()
        extractor.process_articles()
    except Exception as e:
        print(f"\n!!! 主程序异常 !!!: {str(e)}")
        print("\n解决方案建议:")
        print("1. 检查config.py中的API配置")
        print("2. 确认已开通百度NLP服务")
        print("3. 查看详细日志输出")


if __name__ == "__main__":
    main()