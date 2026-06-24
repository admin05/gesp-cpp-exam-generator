# C++ 竞赛训练平台应用

`online_exam/` 是本地在线考试应用代码和结构化题库目录。平台按题库 profile 组卷，
目前内置：

- `literacy`：素养大赛，范围以 `素养大赛/复赛 决赛考点大纲.pdf` 的 C++ 考点为准。
- `csp_j_round1`：CSP-J 第一轮，范围以 `CSP/学习资料/NOI竞赛大纲_Syllabus_Edition_2025.pdf` 中 CSP-J 的 C++ 要求为准，默认只抽客观题。
- `csp_j_round2`：CSP-J 第二轮，范围以同一 NOI 2025 大纲中 CSP-J 的 C++ 要求为准，默认只抽编程题。
- `gesp`、`fuzhou`、`all`：保留已有导入题库和全量练习入口。

## 添加题目

结构化题目放在 `question_bank.py` 或其导入模块中。建议字段：

```python
{
    "id": "csp-j-r1-example-001",
    "competition": "csp_j_round1",
    "category": "程序阅读",
    "difficulty": 3,
    ...
}
```

编程题使用 `competition: "csp_j_round2"`。如果是通用 C++ 基础题，可以使用
`competition: "general"`，它会进入素养大赛、CSP-J、GESP 等基础训练池。

原始 PDF、DOCX、PPT、压缩包等资料目录由仓库根目录 `.gitignore` 忽略，不要直接把
大体积原始资料提交进 Git。先提取、校验、规范化为结构化题目，再提交应用数据。

## 本地运行

```bash
python3 -m online_exam.app
```

默认监听 `0.0.0.0:8000`，可用环境变量覆盖：

- `EXAM_DB`
- `JUDGE_DIR`
- `HOST`
- `PORT`
