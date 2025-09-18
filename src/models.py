from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from datetime import datetime, timedelta
import pytz
from threading import Lock

# 设置北京时间时区
beijing_tz = pytz.timezone('Asia/Shanghai')

class User(UserMixin):
    def __init__(self, id, username, password, email=None):
        self.id = id
        self.username = username
        self.email = email
        self.avatar_url = None
        self.register_date = datetime.now(beijing_tz).strftime('%Y-%m-%d')
        self.last_login = None
        self.remember_me = False
        self.set_password(password)

    @property
    def password(self):
        raise AttributeError('密码不可直接读取')

    def set_password(self, password):
        if len(password) < 8:
            raise ValueError("密码至少需要8个字符")
        if not any(c.isupper() for c in password):
            raise ValueError("密码必须包含大写字母")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def update_last_login(self):
        self.last_login = datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M')

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f'<User {self.username}>'

# 线程安全的数据存储
users_lock = Lock()
users = {
    1: User(1, "admin", "Admin@123"),
    2: User(2, "user", "User@123")
}
password_reset_tokens = {}

def register_user(username, password, email=None):
    with users_lock:
        if any(u.username == username for u in users.values()):
            raise ValueError("用户名已存在")
        user_id = max(users.keys(), default=0) + 1
        new_user = User(user_id, username, password, email)
        users[user_id] = new_user
        return new_user

def get_user_by_username(username):
    with users_lock:
        return next((u for u in users.values() if u.username == username), None)