# 医学知识图谱驱动的近视防控智能平台

## 代码说明
- 本项目为2025安徽省大数据与人工智能应用竞赛创意组初赛作品，基于医学知识图谱实现近视防控智能问答与方案推荐。
- 代码含知识图谱构建、智能问答核心模块，结构清晰，可快速部署验证功能。

## 目录说明
- `src`：代码文件（爬虫、知识图谱、问答逻辑）
- `data`：原始数据与依赖清单`requirements.txt`
- `saved_models`：知识图谱嵌入、问答模型成果
- `user_model`：最终生成的核心模型文件

## 代码使用说明
1. 环境搭建：`pip install -r data/requirements.txt`
2. 运行知识图谱构建：`python src/kg_builder.py`
3. 启动问答服务：`python src/qa_system.py`
