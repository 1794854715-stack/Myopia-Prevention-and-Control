import re
from datetime import datetime
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MyopiaKnowledgeBase:
    def __init__(self, file_path='myopia_knowledge.txt'):
        self.file_path = str(Path(file_path).absolute())  # 转换为绝对路径
        self.knowledge = {}
        self.qa_history = []
        self._load_knowledge()

        # 关键词映射（类级别常量）
        self.KEYWORD_MAPPING = {
            '原因': '病因',
            '为什么': '病因',
            '预防': '预防措施',
            '怎么办': '预防措施',
            '症状': '症状表现',
            '表现': '症状表现',
            '治疗': '治疗方法',
            '怎么治': '治疗方法',
            '诊断': '诊断方法',
            '检查': '诊断方法',
            '并发症': '并发症',
            '危害': '并发症',
            '阿托品': '治疗方法',
            'OK镜': '治疗方法',
            '激光': '治疗方法'
        }

    def _load_knowledge(self):
        """加载知识库文件"""
        try:
            if not Path(self.file_path).exists():
                logger.warning("知识库文件不存在: %s", self.file_path)
                return

            current_section = None
            with open(self.file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # 使用正则表达式匹配章节标题
                    section_match = re.match(r'^\[(.+)\]$', line)
                    if section_match:
                        current_section = section_match.group(1)
                        self.knowledge[current_section] = []
                    elif current_section:
                        self.knowledge[current_section].append(line)

            # 使用传统字符串格式化替代f-string
            logger.info("知识库加载完成，共加载 %d 个分类", len(self.knowledge))

        except Exception as e:
            logger.error("加载知识库失败: %s", str(e))
            self.knowledge = {}

    def get_answer(self, question):
        """根据问题获取答案"""
        if not question.strip():
            return "问题不能为空"

        # 识别问题类型
        question_type = self._identify_question_type(question)

        # 获取答案
        answer = self._generate_answer(question_type, question)

        # 记录历史（使用datetime.isoformat()替代strftime）
        self._record_history(question, answer)

        return answer

    def _identify_question_type(self, question):
        """识别问题类型"""
        question_lower = question.lower()
        for kw, section in self.KEYWORD_MAPPING.items():
            if kw in question_lower:
                return section
        return self._guess_question_type(question)

    def _guess_question_type(self, question):
        """猜测问题类型"""
        question_lower = question.lower()
        if any(kw in question_lower for kw in ['怎么', '如何']):
            return '预防措施'
        elif any(kw in question_lower for kw in ['为什么', '原因']):
            return '病因'
        return None

    def _generate_answer(self, question_type, question):
        """生成答案"""
        if question_type and question_type in self.knowledge:
            # 使用join替代多次字符串拼接
            answer_lines = [
                "关于近视的{}：".format(question_type),
                *self.knowledge[question_type]
            ]
            return "\n".join(answer_lines)

        # 默认回答
        default_answers = {
            '原因': "近视可能由遗传因素、长时间近距离用眼、户外活动不足等原因引起",
            '预防': "预防近视建议：保持正确姿势、定时休息、增加户外活动",
            '症状': "近视常见症状包括视力模糊、眼疲劳、头痛等",
            '治疗': "近视治疗方式包括佩戴眼镜、角膜塑形镜、激光手术等"
        }

        for kw in self.KEYWORD_MAPPING:
            if kw in question:
                return default_answers.get(self.KEYWORD_MAPPING[kw],
                                           "未找到相关信息，您可以询问关于近视的：原因、预防、症状、治疗或诊断方法")

        return "未找到相关信息，您可以询问关于近视的：原因、预防、症状、治疗或诊断方法"

    def _record_history(self, question, answer):
        """记录问答历史"""
        self.qa_history.append({
            'timestamp': datetime.now().isoformat(sep=' ', timespec='minutes'),
            'question': question,
            'answer': answer
        })

    def get_history(self, limit=5):
        """获取最近的问答历史"""
        return self.qa_history[-limit:][::-1]  # 返回倒序，最新的在前


# 示例使用
if __name__ == "__main__":
    try:
        kb = MyopiaKnowledgeBase()
        print("近视知识问答系统已启动 (输入q退出)")

        while True:
            try:
                question = input("\n请输入您关于近视的问题：").strip()
                if question.lower() == 'q':
                    break

                answer = kb.get_answer(question)
                print("\n回答：")
                print(answer)

                # 显示历史记录
                print("\n最近问答记录：")
                for idx, item in enumerate(kb.get_history(3), 1):
                    print("{}. [{}] Q: {}".format(
                        idx,
                        item['timestamp'],
                        item['question'][:20] + ('...' if len(item['question']) > 20 else '')
                    ))
                    print("   A: {}".format(item['answer'].split('\n')[0][:50] + '...'))

            except KeyboardInterrupt:
                print("\n退出系统...")
                break
            except Exception as e:
                logger.error("处理问题时出错: %s", str(e))
                print("系统出现错误，请重新输入问题")

    except Exception as e:
        logger.error("系统初始化失败: %s", str(e))
        print("系统初始化失败，请检查知识库文件")