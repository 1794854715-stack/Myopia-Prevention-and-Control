from neo4j import GraphDatabase, basic_auth  # 修改1: 添加basic_auth导入
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from neo4j_utils import neo4j_driver
from models import User, users, register_user, get_user_by_username
import os
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import timedelta, datetime
import pytz
import logging
import threading
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin
import json
from pathlib import Path
from dotenv import load_dotenv  # 修改2: 添加dotenv导入
from deepseek_qa_system import DeepSeekChatBot

load_dotenv()

# 初始化 Flask 应用
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'your-secret-key-here'

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置文件上传
UPLOAD_FOLDER = 'static/uploads/avatars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # 2MB
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=1),
    TEMPLATES_AUTO_RELOAD=True
)

# 初始化 Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # 设置登录视图端点
login_manager.login_message = "请先登录以访问该页面"
login_manager.login_message_category = "info"

# 设置北京时间时区
beijing_tz = pytz.timezone('Asia/Shanghai')

# 爬取配置
SCRAPE_URL = "http://www.shsyf.com/近视防控"
DATA_FILE = "myopia_data.json"


# 扩展 Neo4j 驱动功能
class EnhancedNeo4jDriver:
    def __init__(self, driver):
        self.driver = driver

    def run_query(self, query, parameters=None):
        """执行Cypher查询"""
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters)
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"查询执行失败: {str(e)}")
            return None

    def session(self):
        """获取数据库会话"""
        return self.driver.session()

    def load_keywords_data(self):
        return self.driver.load_keywords()

    def get_user_history(self, user_id):
        """获取用户历史记录"""
        query = """
        MATCH (u:User {id: $user_id})-[:ASKED]->(q:Question)-[:HAS_ANSWER]->(a:Answer)
        RETURN q.text AS question, a.text AS answer, q.timestamp AS timestamp
        ORDER BY q.timestamp DESC
        LIMIT 10
        """
        return self.run_query(query, {'user_id': str(user_id)})

    def save_user_history(self, user_id, question, answer):
        """保存用户历史记录"""
        query = """
        MERGE (u:User {id: $user_id})
        CREATE (q:Question {text: $question, timestamp: datetime()})
        CREATE (a:Answer {text: $answer})
        CREATE (u)-[:ASKED]->(q)-[:HAS_ANSWER]->(a)
        """
        self.run_query(query, {
            'user_id': str(user_id),
            'question': question,
            'answer': answer
        })



# 包装原始 neo4j_driver
neo4j_driver = EnhancedNeo4jDriver(neo4j_driver)
# 加载提取出的关键字到neo4j数据库中
# neo4j_driver.load_keywords_data()

# 调用deepseek实现问答机器人
API_KEY = "sk-390ca58d89df4f7bbffaee0200f8b754"
bot = DeepSeekChatBot(API_KEY)

class MyopiaScraper:
    def __init__(self, base_url=SCRAPE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def scrape_site(self):
        try:
            logger.info("开始爬取近视防控知识...")
            knowledge = self._scrape_knowledge()
            qa_pairs = self._scrape_qa()

            data = {
                'knowledge': knowledge,
                'qa_pairs': qa_pairs,
                'timestamp': str(datetime.now(beijing_tz))
            }

            self._save_data(data)
            return data
        except Exception as e:
            logger.error(f"爬取过程中出错: {str(e)}")
            return None

    def _scrape_knowledge(self):
        categories = ['原因', '预防', '症状', '治疗', '诊断', '并发症']
        knowledge = {cat: [] for cat in categories}

        try:
            response = self.session.get(self.base_url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            for cat in categories:
                section = soup.find('h2', string=cat)
                if section:
                    items = section.find_next('ul').find_all('li')
                    knowledge[cat] = [item.get_text(strip=True) for item in items]

            return knowledge
        except Exception as e:
            logger.error(f"知识库爬取失败: {str(e)}")
            return knowledge

    def _scrape_qa(self):
        try:
            qa_url = urljoin(self.base_url, "qa")
            response = self.session.get(qa_url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            qa_pairs = []
            qa_items = soup.select('.qa-item')

            for item in qa_items:
                question = item.select_one('.question').get_text(strip=True)
                answer = item.selsect_one('.answer').get_text(strip=True)
                qa_pairs.append({'question': question, 'answer': answer})

            return qa_pairs
        except Exception as e:
            logger.error(f"问答数据爬取失败: {str(e)}")
            return []

    def _save_data(self, data):
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"数据已保存到 {DATA_FILE}")
        except Exception as e:
            logger.error(f"保存数据失败: {str(e)}")


class MyopiaDataProcessor:
    def __init__(self):
        self.driver = neo4j_driver

    def load_data(self):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载数据失败: {str(e)}")
            return None

    def load_extracted_keywords(self):
        self.driver.load_keywords_data()

    def create_graph(self, data):
        if not data:
            logger.error("没有可处理的数据")
            return False

        try:
            # 清除现有数据
            self.driver.run_query("MATCH (n) DETACH DELETE n")

            # 创建基础节点
            queries = [
                "CREATE (:Disease {name: '近视', type: 'disease'})",
                "CREATE (:Disease {name: '高度近视', type: 'disease'})"
            ]

            # 添加知识类别
            for category in ['原因', '预防', '症状', '治疗', '诊断', '并发症']:
                queries.append(f"CREATE (:Category {{name: '{category}'}})")

            # 执行基础查询
            for query in queries:
                self.driver.run_query(query)

            # 添加知识关系
            for category, items in data['knowledge'].items():
                for item in items:
                    query = """
                    MATCH (d:Disease {name: '近视'})
                    MATCH (c:Category {name: $category})
                    MERGE (f:Fact {content: $item})
                    MERGE (d)-[:HAS_KNOWLEDGE]->(f)
                    MERGE (f)-[:BELONGS_TO]->(c)
                    """
                    self.driver.run_query(query, {'category': category, 'item': item})

            # 添加问答数据
            for qa in data['qa_pairs']:
                query = """
                MATCH (d:Disease {name: '近视'})
                CREATE (q:Question {text: $question, timestamp: $ts})
                CREATE (a:Answer {text: $answer})
                CREATE (d)-[:HAS_QUESTION]->(q)-[:HAS_ANSWER]->(a)
                """
                params = {
                    'question': qa['question'],
                    'answer': qa['answer'],
                    'ts': int(datetime.now(beijing_tz).timestamp())
                }
                self.driver.run_query(query, params)

            logger.info("知识图谱构建成功")
            return True
        except Exception as e:
            logger.error(f"构建图谱失败: {str(e)}")
            return False


def create_upload_dir():
    """确保上传目录存在"""
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def get_beijing_time():
    return datetime.now(beijing_tz)


def get_2025_beijing_time():
    return datetime(2025, 1, 1, tzinfo=beijing_tz)


def extract_keywords(question):
    """从问题中提取关键词"""
    keywords = []
    keyword_map = {
        '原因': '原因', '为什么': '原因', '成因': '原因',
        '预防': '预防', '避免': '预防', '防止': '预防',
        '症状': '症状', '表现': '症状', '特征': '症状',
        '治疗': '治疗', '治愈': '治疗', '疗法': '治疗',
        '诊断': '诊断', '检查': '诊断', '验光': '诊断',
        '并发症': '并发症', '后遗症': '并发症', '危害': '并发症'
    }

    kids_keywords = {
        '看不清': '症状', '眼睛累': '症状', '怕光': '症状',
        '揉眼睛': '症状', '眯眼睛': '症状', '头痛': '症状',
        '看电视近': '症状', '抄作业慢': '症状', '眼睛痒': '症状',
        '不想看书': '症状', '黑板模糊': '症状', '眼睛痛': '症状'
    }
    question_lower = question.lower()
    for kw in keyword_map:
        if kw in question_lower:
            keywords.append(keyword_map[kw])
    return keywords if keywords else ['近视']


def convert_time_format(original_str):
    # 去除时区部分并替换 T 为空格
    dt_str = original_str.split('+')[0].replace('T', ' ')

    # 分离日期时间与微秒（处理 9 位微秒）
    if '.' in dt_str:
        main_part, fractional = dt_str.split('.')
        fractional = fractional.ljust(9, '0')[:6]  # 截断或补零至 6 位
        dt_str = f"{main_part}.{fractional}"
    else:
        dt_str += ".000000"

    # 解析为 datetime 对象
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")

    # 格式化为目标字符串
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")

def generate_cypher_query(keywords):
    """根据关键词生成Cypher查询"""
    if not keywords:
        return None

    query_template = """
    MATCH (n:Knowledge)
    WHERE ANY(keyword IN $keywords WHERE n.text CONTAINS keyword)
    RETURN n.text AS result
    LIMIT 5
    """
    return query_template


def generate_answer(results, keywords, question):
    """增强版回答生成"""
    if results:
        return "相关信息：\n" + "\n".join(["- {}".format(r['result']) for r in results])

    # default_answers = {
    #     '原因': "近视可能由遗传因素、长时间近距离用眼、户外活动不足等原因引起",
    #     '预防': "预防近视建议：保持正确姿势、定时休息、增加户外活动",
    #     '症状': "近视常见症状包括视力模糊、眼疲劳、头痛等",
    #     '治疗': "近视治疗方式包括佩戴眼镜、角膜塑形镜、激光手术等",
    #     '诊断': "近视诊断方法包括视力检查、验光、眼底检查等",
    #     '并发症': "近视可能引发视网膜脱落、青光眼等并发症"
    # }

    # for kw in keywords:
    #     if kw in default_answers:
    #         return default_answers[kw]

    # 根据关键字和问题进行回答
    # 第一轮对话（非流式）
    keywords_str = '，'.join(keywords)
    response = bot.chat(question + f"问题关键字：{keywords_str}")
    for msg in bot.messages:
        print(f"{msg['role']}: {msg['content'][:50]}...")
    return response

    # return "没有找到相关信息，您可以尝试询问近视的原因、预防、症状、治疗或诊断方法"


@login_manager.user_loader
def load_user(user_id):
    """加载用户"""
    return users.get(int(user_id))


# ====================== 路由定义 ======================
@app.route('/')
def index():
    """根路径自动重定向到登录页面"""
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if current_user.is_authenticated:
        return redirect(url_for('main'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        remember = 'remember' in request.form

        if not username or not password:
            flash('用户名和密码不能为空', 'danger')
            return redirect(url_for('login'))

        user = get_user_by_username(username)
        # 关键修改：使用 check_password 方法替代直接访问 password 属性
        if user and hasattr(user, 'check_password') and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash('登录成功', 'success')
            return redirect(next_page or url_for('main'))
        else:
            flash('用户名或密码错误', 'danger')

    return render_template('login.html', current_year=get_2025_beijing_time().year)


@app.route('/main')
@login_required
def main():
    """主界面"""
    return render_template('main.html',
                           user=current_user,
                           current_year=get_2025_beijing_time().year)


@app.route('/user-center')
@login_required
def user_center():
    """用户中心"""
    try:
        # 从Neo4j获取历史记录
        neo4j_history = neo4j_driver.get_user_history(current_user.id) or []

        # 格式化时间戳
        for record in neo4j_history:
            if 'timestamp' in record:
                try:
                    # dt = datetime.strptime(record['timestamp'], '%Y-%m-%dT%H:%M:%S.%f%z')
                    record['formatted_time'] = record['timestamp']
                except:
                    record['formatted_time'] = record['timestamp']

        return render_template('user_center.html',
                               user=current_user,
                               history=neo4j_history,
                               current_year=get_2025_beijing_time().year)
    except Exception as e:
        logger.error("用户中心加载失败: %s", str(e))
        flash('加载用户中心失败', 'danger')
        return redirect(url_for('main'))


@app.route('/light-detection')
@login_required
def light_detection():
    return render_template('light_detection.html',
                           user=current_user,
                           current_year=get_2025_beijing_time().year)


@app.route('/index')
@login_required
def qa_index():
    return render_template('index.html',
                           user=current_user,
                           current_year=get_2025_beijing_time().year)


@app.route('/ask', methods=['POST'])
@login_required
def ask():
    """处理用户提问"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()

        if not question:
            return jsonify({'error': '问题不能为空'}), 400

        # 生成回答
        keywords = extract_keywords(question)
        print("关键字：", keywords)
        query = generate_cypher_query(keywords)

        # 执行查询
        results = neo4j_driver.run_query(query, {'keywords': keywords}) if query else []
        answer = generate_answer(results, keywords, question)
        # 保存到Neo4j历史记录
        neo4j_driver.save_user_history(current_user.id, question, answer)

        return jsonify({
            'answer': answer,
            'question': question,
            'timestamp': datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        logger.error(f"问答处理失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history', methods=['GET'])
@login_required
def get_history():
    """获取用户历史记录API"""
    try:
        history = neo4j_driver.get_user_history(current_user.id) or []
        # 格式化时间
        for record in history:
            if 'timestamp' in record:
                try:
                    # dt = datetime.strptime(record['timestamp'], '%Y-%m-%dT%H:%M:%S.%f%z')
                    # print("dt=", dt)
                    # print("time=", record['timestamp'])
                    # print("date=", datetime.now())
                    # print("type", type(record['timestamp']))
                    date_time = record['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
                    new_time = convert_time_format(date_time)
                    record['timestamp'] = new_time
                except:
                    record['formatted_time'] = record['timestamp']
        return jsonify({'history': history})
    except Exception as e:
        logger.error(f"获取历史记录失败: {str(e)}")
        return jsonify({'error': str(e)}), 10


@app.route('/update-knowledge', methods=['POST'])
@login_required
def update_knowledge():
    """更新知识库"""

    def scrape_task():
        try:
            scraper = MyopiaScraper()
            data = scraper.scrape_site()
            if data:
                processor = MyopiaDataProcessor()
                processor.create_graph(data)

        except Exception as e:
            logger.error(f"知识库更新失败: {str(e)}")

    thread = threading.Thread(target=scrape_task)
    thread.start()
    return jsonify({'success': True, 'message': '知识库更新任务已启动'})


@app.route('/register', methods=['GET', 'POST'])
def register():
    """注册页面"""
    if current_user.is_authenticated:
        return redirect(url_for('main'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not username or not password:
            flash('用户名和密码不能为空', 'danger')
            return redirect(url_for('register'))

        if len(username) < 4 or len(username) > 16:
            flash('用户名长度需在4-16个字符之间', 'danger')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('两次输入的密码不一致', 'danger')
            return redirect(url_for('register'))

        if len(password) < 8:
            flash('密码长度至少需要8位', 'danger')
            return redirect(url_for('register'))

        if get_user_by_username(username):
            flash('该用户名已被注册', 'danger')
            return redirect(url_for('register'))

        try:
            new_user = register_user(username, password)
            flash('注册成功，请登录', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            logger.error(f"用户注册失败: {str(e)}")
            flash('注册失败，请稍后再试', 'danger')

    return render_template('register.html', current_year=get_2025_beijing_time().year)


@app.route('/logout')
@login_required
def logout():
    """增强版退出登录处理"""
    try:
        # 1. 清除Flask-Login会话
        logout_user()

        # 2. 清除Flask会话数据
        session.clear()

        # 3. 添加响应头防止缓存
        response = redirect(url_for('login'))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        # 4. 添加时间戳参数防止重定向缓存
        login_url = url_for('login', _external=True) + f"?t={int(datetime.now().timestamp())}"
        response.headers['Location'] = login_url

        # 5. 记录日志
        logger.info(f"用户 {current_user.username} 已退出登录")

        return response
    except Exception as e:
        logger.error(f"退出登录失败: {str(e)}")
        flash('退出登录时出错', 'danger')
        return redirect(url_for('main'))

@app.route('/api/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    """处理头像上传"""
    try:
        if 'avatar' not in request.files:
            return jsonify({'error': '没有选择文件'}), 400

        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400

        if not (file and allowed_file(file.filename)):
            return jsonify({'error': '不允许的文件类型'}), 400

        create_upload_dir()
        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"user_{current_user.id}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # 删除旧头像
        old_avatar = current_user.avatar_url
        if old_avatar and os.path.exists(old_avatar.replace('/static/', '')):
            try:
                os.remove(old_avatar.replace('/static/', ''))
            except Exception as e:
                logger.error(f"删除旧头像失败: {str(e)}")

        file.save(filepath)
        current_user.avatar_url = f"/static/uploads/avatars/{filename}"

        return jsonify({
            'avatar_url': current_user.avatar_url,
            'message': '头像上传成功'
        })
    except Exception as e:
        logger.error(f"头像上传失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 童趣版游戏题库
KIDS_QUESTIONS = [
    {
        "id": 1,
        "question": "每天户外活动多久对眼睛最好？",
        "options": ["15分钟", "1小时", "2小时", "不出门"],
        "answer": 2,
        "explanation": "小博士说：每天2小时户外活动能让眼睛放松，预防近视哦！"
    },
    {
        "id": 2,
        "question": "看书时应该保持多远距离？",
        "options": ["10厘米", "30厘米", "50厘米", "越远越好"],
        "answer": 1,
        "explanation": "记住'一尺一拳一寸'：眼睛离书一尺(33cm)，胸离桌一拳，手离笔尖一寸！"
    },
    {
        "id": 3,
        "question": "哪种光线最适合阅读？",
        "options": ["昏暗的台灯", "刺眼的强光", "柔和的自然光", "闪烁的灯光"],
        "answer": 2,
        "explanation": "柔和的自然光最护眼，太暗或太亮都会让眼睛疲劳哦！"
    },
    {
        "id": 4,
        "question": "用眼多久应该休息一下？",
        "options": ["10分钟", "20分钟", "1小时", "不用休息"],
        "answer": 1,
        "explanation": "20-20-20法则：每20分钟看20英尺(6米)外20秒！"
    },
    {
        "id": 5,
        "question": "哪种食物对眼睛最有益？",
        "options": ["糖果", "炸鸡", "胡萝卜", "冰淇淋"],
        "answer": 2,
        "explanation": "胡萝卜富含维生素A，是眼睛的好朋友！但也要均衡饮食哦~"
    },
    {
        "id": 6,
        "question": "哪种姿势看书最不好？",
        "options": ["坐直看书", "躺着看书", "站着看书", "趴着看书"],
        "answer": 1,
        "explanation": "躺着看书会让眼睛很累，容易近视！要坐端正哦！"
    },
    {
        "id": 7,
        "question": "晚上睡觉前应该？",
        "options": ["玩手机游戏", "看动画片", "做眼保健操", "关灯睡觉"],
        "answer": 3,
        "explanation": "睡前要关灯，黑暗环境让眼睛充分休息！"
    },
    {
        "id": 8,
        "question": "哪种颜色的光最伤眼睛？",
        "options": ["蓝色", "绿色", "红色", "黄色"],
        "answer": 0,
        "explanation": "蓝光会伤害视网膜，晚上要少看电子屏幕！"
    },
    {
        "id": 9,
        "question": "做眼保健操应该？",
        "options": ["用力按压眼睛", "轻轻按摩穴位", "随便揉揉", "不用洗手"],
        "answer": 1,
        "explanation": "要洗手后轻轻按摩正确穴位才有效哦！"
    },
    {
        "id": 10,
        "question": "近视了应该怎么办？",
        "options": ["不戴眼镜", "随便借别人的眼镜", "及时去医院检查", "自己买眼镜"],
        "answer": 2,
        "explanation": "发现视力下降要及时去医院，医生会给出专业建议！"
    }
]

@app.route('/kids_game')
@login_required
def kids_game():
    """护眼小勇士游戏页面"""
    return render_template('kids_game.html',
                         user=current_user,
                         current_year=get_2025_beijing_time().year)


@app.route('/api/kids-game/questions')
@login_required
def get_kids_game_questions():
    """获取童趣游戏题目"""
    try:
        return jsonify({
            'success': True,
            'questions': KIDS_QUESTIONS,
            'total': len(KIDS_QUESTIONS)
        })
    except Exception as e:
        logger.error(f"获取童趣游戏题目失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ====================== 主程序 ======================
if __name__ == '__main__':
    create_upload_dir()

    # Neo4j连接检查
    try:
        with neo4j_driver.session() as session:
            result = session.run("RETURN 1 AS status")
            if result.single()["status"] == 1:
                logger.info("✅ Neo4j连接验证成功")
    except Exception as e:
        logger.error(f"Neo4j连接失败: {str(e)}")
        # 生产环境建议终止启动
        # sys.exit(1)


    app.run(host='0.0.0.0', port=5000, debug=True)
