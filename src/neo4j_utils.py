from neo4j import GraphDatabase
from config import NEO4J_CONFIG, FILE_PATHS
import json

class Neo4jDriver:
    def __init__(self, uri, user, password):
        """
        初始化 Neo4j 连接。
        :param uri: Neo4j 数据库的 URI，例如 "bolt://localhost:7687"
        :param user: 用户名
        :param password: 密码
        """
        self._uri = uri
        self._user = user
        self._password = password
        self._driver = None

    def connect(self):
        """
        连接到 Neo4j 数据库。
        """
        try:
            self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
            print("成功连接到 Neo4j 数据库！")
            return True
        except Exception as e:
            print(f"连接失败：{e}")
            return False

    def close(self):
        """
        关闭数据库连接。
        """
        if self._driver is not None:
            self._driver.close()
            print("数据库连接已关闭。")

    def get_session(self):
        """
        获取数据库会话（新增方法解决'session'属性错误）
        :return: Neo4j 会话对象
        """
        if self._driver is None:
            self.connect()
        return self._driver.session()

    def run_query(self, query, parameters=None):
        """
        执行 Cypher 查询。
        :param query: Cypher 查询语句
        :param parameters: 查询参数（可选）
        :return: 查询结果列表
        """
        try:
            with self.get_session() as session:  # 使用get_session方法
                result = session.run(query, parameters)
                return [dict(record) for record in result]  # 转换为字典列表
        except Exception as e:
            print(f"查询失败：{e}")
            return None

    def test_connection(self):
        """
        测试数据库连接是否正常。
        :return: 布尔值表示连接是否成功
        """
        try:
            with self.get_session() as session:  # 使用get_session方法
                result = session.run("RETURN '连接成功' AS message")
                print(result.single()["message"])
            return True
        except Exception as e:
            print(f"连接测试失败：{e}")
            return False

    def session(self):
        """
        兼容旧代码的session方法（解决错误的关键）
        """
        return self.get_session()

    def load_keywords(self):
        """加载关键词数据到Neo4j"""
        with open(FILE_PATHS['output_json'], 'r', encoding='utf-8') as f:
            keyword_data = json.load(f)

        with self._driver.session() as session:
            for item in keyword_data:
                # 创建文章节点（包含更多元数据）
                session.run("""
                   MERGE (a:Article {id: $article_id})
                   SET a.title = $title,
                       a.url = $url,
                       a.source = $source
                   """, {
                    'article_id': item['article_id'],
                    # 'article_id': item['id'],
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
                        # 'article_id': item['id']
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
                        # 'article_id': item['id'],
                        'score': float(score)
                    })

        print(f"成功导入 {len(keyword_data)} 篇文章的关键词到Neo4j")


# 数据库连接信息
uri = "bolt://localhost:7687"  # Neo4j 地址
username = "neo4j"             # 用户名
password = "12345678"          # 密码

# 创建 Neo4j 驱动实例
# neo4j_driver = Neo4jDriver(uri, username, password)
neo4j_driver = Neo4jDriver(NEO4J_CONFIG['uri'], NEO4J_CONFIG['user'], NEO4J_CONFIG['password'])
neo4j_driver.connect()  # 连接到数据库
neo4j_driver.test_connection()
# neo4j_driver.load_keywords()
