from neo4j import GraphDatabase
from config import NEO4J_CONFIG, FILE_PATHS
import json


class Neo4jKeywordLoader:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            NEO4J_CONFIG['uri'],
            auth=(NEO4J_CONFIG['user'], NEO4J_CONFIG['password'])
        )

    def create_constraints(self):
        """创建Neo4j约束"""
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Article) REQUIRE a.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (k:Keyword) REQUIRE k.name IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Source) REQUIRE s.name IS UNIQUE")

    def load_keywords(self):
        """加载关键词数据到Neo4j"""
        with open(FILE_PATHS['output_json'], 'r', encoding='utf-8') as f:
            keyword_data = json.load(f)

        with self.driver.session() as session:
            for item in keyword_data:
                # 创建文章节点（包含更多元数据）
                session.run("""
                MERGE (a:Article {id: $article_id})
                SET a.title = $title,
                    a.url = $url,
                    a.source = $source
                """, {
                    'article_id': item['article_id'],
                    'title': item['title'],
                    'url': item.get('url', ''),
                    'source': item.get('source', '')
                })

                # 创建来源节点（如果存在）
                if item.get('source'):
                    session.run("""
                    MERGE (s:Source {name: $source_name})
                    MERGE (a:Article {id: $article_id})
                    MERGE (a)-[:FROM_SOURCE]->(s)
                    """, {
                        'source_name': item['source'],
                        'article_id': item['article_id']
                    })

                # 创建关键词节点和关系
                for keyword, score in zip(item['keywords'], item['scores']):
                    session.run("""
                    MERGE (k:Keyword {name: $keyword})
                    MERGE (a:Article {id: $article_id})
                    MERGE (a)-[r:HAS_KEYWORD]->(k)
                    SET r.score = $score
                    """, {
                        'keyword': keyword,
                        'article_id': item['article_id'],
                        'score': float(score)
                    })

        print(f"成功导入 {len(keyword_data)} 篇文章的关键词到Neo4j")