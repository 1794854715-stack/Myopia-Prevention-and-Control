from transformers import BertTokenizer, BertModel
import torch
import faiss
import numpy as np
from neo4j import GraphDatabase
from config import BERT_CONFIG, NEO4J_CONFIG


class BertQASystem:
    def __init__(self):
        # 初始化BERT模型
        self.tokenizer = BertTokenizer.from_pretrained(BERT_CONFIG['model_name'])
        self.model = BertModel.from_pretrained(BERT_CONFIG['model_name'])
        self.model.eval()

        # 初始化Neo4j连接
        self.neo4j_driver = GraphDatabase.driver(
            NEO4J_CONFIG['uri'],
            auth=(NEO4J_CONFIG['user'], NEO4J_CONFIG['password'])
        )

        # 关键词映射表
        self.keyword_map = {
            '近视': 'myopia', '预防': 'prevention', '治疗': 'treatment',
            '症状': 'symptom', '原因': 'cause', '儿童': 'children'
        }

    def encode_text(self, text):
        """编码文本为BERT向量"""
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=64)
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state[:, 0, :].numpy()

    def get_keyword_answer(self, keywords):
        """基于关键词获取答案"""
        with self.neo4j_driver.session() as session:
            result = session.run("""
            MATCH (k:Keyword)-[:HAS_KEYWORD]-(a:Article)
            WHERE k.name IN $keywords
            RETURN a.title AS title, COUNT(*) AS count
            ORDER BY count DESC
            LIMIT 3
            """, {'keywords': keywords})

            articles = [dict(record) for record in result]

        if articles:
            return f"推荐阅读：{'、'.join([a['title'] for a in articles])}"
        return "未找到相关信息，请尝试其他问题"

    def answer_question(self, question):
        """回答用户问题"""
        # 提取关键词
        keywords = [self.keyword_map.get(kw, kw)
                    for kw in question if kw in self.keyword_map]

        # 获取答案
        answer = self.get_keyword_answer(keywords)

        return {
            'answer': answer,
            'keywords': keywords
        }