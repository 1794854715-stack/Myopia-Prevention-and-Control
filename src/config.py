# 百度云API配置
BAIDU_API = {
    'api_key': '8ghTrm26Ovsd4OW5DJzL8gp9',
    'secret_key': 'cOUdM3XJ9YqBfINOPtZ2uiSNffLrkeqo',
    'keyword_url': 'https://aip.baidubce.com/rpc/2.0/nlp/v1/txt_keywords_extraction',
    'auth_url': 'https://aip.baidubce.com/oauth/2.0/token'
}

# Neo4j数据库配置
NEO4J_CONFIG = {
    'uri': 'bolt://localhost:7687',
    'user': 'neo4j',
    'password': '12345678'
}

LOCAL_MODE = True

# BERT模型配置
BERT_CONFIG = {
    'model_name': 'google-bert/bert-base-chinese',
    'faiss_index_path': 'faiss_index'
}

# 文件路径配置
FILE_PATHS = {
    'input_json': 'myopia_articles.json',  # 您的原始数据文件
    # 'output_json': 'processed_keywords.json'
    'output_json': 'extracted_keywords.json'
}

LOCAL_FALLBACK = {
    "enable": False,  # 设置为True时允许使用本地算法
    "require_jieba": True  # 是否需要jieba分词
}