from __future__ import annotations

import html
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .question_bank import CHOICE_QUESTIONS, PROGRAMMING_TASKS
from .question_generators import build_generated_tests, has_generator, missing_generator_ids


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("EXAM_DB", "/data/exam.db"))
JUDGE_DIR = Path(os.environ.get("JUDGE_DIR", "/judge"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                student_name TEXT NOT NULL,
                choice_score INTEGER NOT NULL,
                choice_total INTEGER NOT NULL,
                program_score INTEGER NOT NULL,
                program_total INTEGER NOT NULL,
                detail TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(exam_id) REFERENCES exams(id)
            )
            """
        )


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def h(value: object) -> str:
    return html.escape(str(value), quote=True)


def normalize_output(value: str) -> str:
    lines = value.replace("\r\n", "\n").replace("\r", "\n").strip().split("\n")
    return "\n".join(line.rstrip() for line in lines).strip()


def balanced_pick(items: list[dict], count: int, min_difficulty: int = 0) -> list[dict]:
    if count <= 0:
        return []
    pool = [item for item in items if item.get("difficulty", 0) >= min_difficulty]
    if len(pool) < count:
        picked_ids = {item["id"] for item in pool}
        pool.extend(item for item in items if item["id"] not in picked_ids)
    limit = min(count, len(pool))
    grouped: dict[str, list[dict]] = {}
    for item in pool:
        grouped.setdefault(item["category"], []).append(item)

    rng = random.SystemRandom()
    for bucket in grouped.values():
        rng.shuffle(bucket)

    selected: list[dict] = []
    categories = list(grouped)
    rng.shuffle(categories)
    while len(selected) < limit and categories:
        remaining_categories = []
        for category in categories:
            bucket = grouped[category]
            if bucket and len(selected) < limit:
                selected.append(bucket.pop())
            if bucket:
                remaining_categories.append(category)
        categories = remaining_categories
        rng.shuffle(categories)
    rng.shuffle(selected)
    return selected


def prepare_programming_task(task: dict) -> dict:
    prepared = dict(task)
    if not has_generator(task["id"]):
        public_tests = prepared.get("public_tests") or prepared["tests"][:1]
        hidden_tests = prepared.get("hidden_tests") or prepared["tests"]
        prepared["public_tests"] = public_tests
        prepared["hidden_tests"] = hidden_tests
        prepared["tests"] = hidden_tests
        return prepared
    generated = build_generated_tests(task)
    prepared["public_tests"] = generated["public_tests"]
    prepared["hidden_tests"] = generated["hidden_tests"]
    prepared["tests"] = generated["hidden_tests"]
    return prepared


def build_exam(
    title: str,
    choice_count: int,
    program_count: int,
    duration: int,
    program_min_difficulty: int = 5,
) -> dict:
    missing_generators = missing_generator_ids(PROGRAMMING_TASKS)
    if missing_generators:
        raise RuntimeError("以下编程题缺少测试生成器：" + ", ".join(missing_generators))
    programming_tasks = [
        prepare_programming_task(task)
        for task in balanced_pick(PROGRAMMING_TASKS, program_count, program_min_difficulty)
    ]
    return {
        "title": title,
        "duration_minutes": duration,
        "principle": "GESP C++ 四级偏上 / 五级入门：表达式、循环、数组字符串、函数递推、排序搜索、筛法质数、贪心枚举与逻辑推理均衡覆盖。",
        "choice_questions": balanced_pick(CHOICE_QUESTIONS, choice_count),
        "programming_tasks": programming_tasks,
    }


def run_cpp_judge(code: str, tests: list[dict]) -> dict:
    if not shutil.which("g++"):
        return {
            "status": "NO_COMPILER",
            "message": "容器内没有找到 g++。",
            "passed": 0,
            "total": len(tests),
            "cases": [],
        }

    JUDGE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gesp-judge-", dir=JUDGE_DIR) as td:
        workdir = Path(td)
        src = workdir / "main.cpp"
        exe = workdir / "main"
        src.write_text(code, encoding="utf-8")

        compile_cmd = ["g++", "-std=c++17", "-O2", "-pipe", str(src), "-o", str(exe)]
        compiled = subprocess.run(
            compile_cmd,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=8,
        )
        if compiled.returncode != 0:
            return {
                "status": "COMPILE_ERROR",
                "message": compiled.stderr[-2000:],
                "passed": 0,
                "total": len(tests),
                "cases": [],
            }
        exe.chmod(0o755)

        cases = []
        passed = 0
        for index, test in enumerate(tests, 1):
            try:
                result = subprocess.run(
                    [str(exe)],
                    input=test["input"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
            except subprocess.TimeoutExpired:
                cases.append(
                    {
                        "index": index,
                        "status": "TLE",
                        "input": test["input"],
                        "expected": test["output"],
                        "actual": "",
                    }
                )
                continue
            except PermissionError as exc:
                return {
                    "status": "SYSTEM_ERROR",
                    "message": f"判题程序无法执行：{exc}",
                    "passed": passed,
                    "total": len(tests),
                    "cases": cases,
                }

            actual = result.stdout
            ok = result.returncode == 0 and normalize_output(actual) == normalize_output(test["output"])
            if ok:
                passed += 1
            cases.append(
                {
                    "index": index,
                    "status": "AC" if ok else ("RE" if result.returncode != 0 else "WA"),
                    "input": test["input"],
                    "expected": test["output"],
                    "actual": actual if result.returncode == 0 else result.stderr[-1000:],
                }
            )

        return {
            "status": "DONE",
            "message": "",
            "passed": passed,
            "total": len(tests),
            "cases": cases,
        }


def layout(title: str, body: str) -> bytes:
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{h(title)}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/">GESP C++ 在线测试</a>
    <nav>
      <a href="/">考试入口</a>
      <a href="/admin">管理后台</a>
    </nav>
  </header>
  <main>{body}</main>
</body>
</html>"""
    return page.encode("utf-8")


def render_code(code: str) -> str:
    if not code:
        return ""
    return f"<pre class=\"code\"><code>{h(code)}</code></pre>"


def answer_indices(answer: object) -> list[int]:
    if isinstance(answer, list):
        return sorted(int(x) for x in answer)
    return [int(answer)]


def answer_label(indices: list[int]) -> str:
    if not indices:
        return "未作答"
    return ", ".join(LETTERS[i] for i in indices if 0 <= i < len(LETTERS))


def render_question_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    content = raw_html
    content = re.sub(r"\sstyle=\"[^\"]*\"", "", content, flags=re.IGNORECASE)
    content = re.sub(r"\sclass=\"[^\"]*\"", "", content, flags=re.IGNORECASE)
    content = re.sub(r"<script\b[^>]*>.*?</script>", "", content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r"<(?!/?(?:p|br|span|strong|b|em|i|code|pre|img)\b)[^>]+>", "", content, flags=re.IGNORECASE)
    content = re.sub(r"<img\b([^>]*)>", _sanitize_img_tag, content, flags=re.IGNORECASE)
    content = re.sub(r"<(p|br|span|strong|b|em|i|code|pre)\b[^>]*>", r"<\1>", content, flags=re.IGNORECASE)
    return f"<div class=\"richtext\">{content}</div>"


def _sanitize_img_tag(match: re.Match[str]) -> str:
    src_match = re.search(r"\bsrc=[\"']([^\"']+)[\"']", match.group(1), flags=re.IGNORECASE)
    if not src_match:
        return ""
    src = src_match.group(1)
    if not src.startswith(("https://cdn2.1717youxue.com/", "https://study.1717youxue.com/")):
        return ""
    return f"<img src=\"{h(src)}\" alt=\"题目图片\" loading=\"lazy\">"


def load_exam(exam_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()


def save_exam(payload: dict) -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO exams(title, duration_minutes, payload, created_at) VALUES (?, ?, ?, ?)",
            (payload["title"], payload["duration_minutes"], json.dumps(payload, ensure_ascii=False), now_text()),
        )
        return int(cur.lastrowid)


def public_home() -> bytes:
    with db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY id DESC").fetchall()

    cards = []
    for exam in exams:
        payload = json.loads(exam["payload"])
        cards.append(
            f"""
            <article class="exam-card">
              <div>
                <h2>{h(exam["title"])}</h2>
                <p>{len(payload["choice_questions"])} 道选择题 · {len(payload["programming_tasks"])} 道编程题 · {exam["duration_minutes"]} 分钟</p>
              </div>
              <a class="button" href="/exam/{exam["id"]}">开始考试</a>
            </article>
            """
        )

    empty = "<p class=\"muted\">还没有试卷。先进入管理后台创建一份。</p>" if not cards else ""
    return layout(
        "考试入口",
        f"""
        <section class="hero compact">
          <h1>GESP C++ 本地在线测试平台</h1>
          <p>按管理员设置自动组卷，考生在线作答，编程题提交 C++ 代码后按样例即时测评。</p>
        </section>
        <section class="panel">
          <div class="section-title">
            <h2>可参加考试</h2>
            <a class="ghost" href="/admin">创建试卷</a>
          </div>
          <div class="exam-list">{''.join(cards)}{empty}</div>
        </section>
        """,
    )


def admin_page(message: str = "") -> bytes:
    with db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY id DESC LIMIT 20").fetchall()

    rows = []
    for exam in exams:
        payload = json.loads(exam["payload"])
        rows.append(
            f"""
            <tr>
              <td>#{exam["id"]}</td>
              <td>{h(exam["title"])}</td>
              <td>{len(payload["choice_questions"])} / {len(payload["programming_tasks"])}</td>
              <td>{h(exam["created_at"])}</td>
              <td class="actions">
                <a href="/exam/{exam["id"]}">考试页</a>
                <a href="/admin/exams/{exam["id"]}">成绩</a>
                <form method="post" action="/admin/exams/{exam["id"]}/delete" onsubmit="return confirm('确定删除这份试卷和所有提交记录吗？');">
                  <button class="link-danger" type="submit">删除</button>
                </form>
              </td>
            </tr>
            """
        )

    notice = f"<div class=\"notice\">{h(message)}</div>" if message else ""
    return layout(
        "管理后台",
        f"""
        <section class="admin-grid">
          <form class="panel form-panel" method="post" action="/admin/exams">
            <h1>创建试卷</h1>
            {notice}
            <label>试卷标题
              <input name="title" value="GESP C++ 四级偏上 / 五级入门模拟测试" required>
            </label>
            <div class="two">
              <label>选择题数量
                <input name="choice_count" type="number" min="0" max="{len(CHOICE_QUESTIONS)}" value="10">
              </label>
              <label>编程题数量
                <input name="program_count" type="number" min="0" max="{len(PROGRAMMING_TASKS)}" value="4">
              </label>
            </div>
            <label>编程题最低难度
              <select name="program_min_difficulty">
                <option value="5" selected>五级入门（推荐）</option>
                <option value="4">四级偏上</option>
              </select>
            </label>
            <label>考试时长（分钟）
              <input name="duration" type="number" min="1" max="240" value="90">
            </label>
            <button class="button primary" type="submit">生成试卷</button>
            <p class="hint">当前题库：{len(CHOICE_QUESTIONS)} 道选择题，{len(PROGRAMMING_TASKS)} 道编程题。组卷会按知识点分类均衡抽取。</p>
          </form>
          <section class="panel">
            <h2>最近试卷</h2>
            <table>
              <thead><tr><th>ID</th><th>标题</th><th>选择/编程</th><th>创建时间</th><th>操作</th></tr></thead>
              <tbody>{''.join(rows) or '<tr><td colspan="5">暂无试卷</td></tr>'}</tbody>
            </table>
          </section>
        </section>
        """,
    )


def exam_page(exam_id: int) -> bytes:
    exam = load_exam(exam_id)
    if not exam:
        return not_found()
    payload = json.loads(exam["payload"])

    nav = []
    choice_html = []
    for i, q in enumerate(payload["choice_questions"], 1):
        nav.append(f"<a href=\"#q{i}\" data-target=\"q{i}\">{i}</a>")
        opts = []
        input_type = "checkbox" if isinstance(q["answer"], list) else "radio"
        for oi, opt in enumerate(q["options"]):
            opts.append(
                f"""
                <label class="option">
                  <input type="{input_type}" name="choice_{i}" value="{oi}">
                  <span>{LETTERS[oi]}. {h(opt)}</span>
                </label>
                """
            )
        choice_html.append(
            f"""
            <section class="question-card" id="q{i}">
              <div class="q-head"><span>选择题 {i}</span><small>{h(q["category"])} · 难度 {q["difficulty"]}</small></div>
              <p>{h(q["stem"])}</p>
              {render_question_html(q.get("content_html", ""))}
              {render_code(q["code"])}
              <div class="options">{''.join(opts)}</div>
            </section>
            """
        )

    program_html = []
    for pi, task in enumerate(payload["programming_tasks"], 1):
        nav.append(f"<a href=\"#p{pi}\" data-target=\"p{pi}\">P{pi}</a>")
        public_tests = task.get("public_tests") or task["tests"][:1]
        hidden_tests = task.get("hidden_tests") or task["tests"]
        test_label = f"公开样例 {len(public_tests)} 组 · 隐藏测试 {len(hidden_tests)} 组"
        sample_note = (
            "页面仅显示公开样例，提交后使用隐藏测试评分。"
            if hidden_tests
            else "原始资料未提供可抽取样例，本题仅展示题面用于练习讲解。"
        )
        samples = "".join(
            f"<tr><td>{idx}</td><td><pre>{h(t['input'])}</pre></td><td><pre>{h(t['output'])}</pre></td></tr>"
            for idx, t in enumerate(public_tests, 1)
        )
        program_html.append(
            f"""
            <section class="question-card" id="p{pi}">
              <div class="q-head"><span>编程题 {pi}. {h(task["title"])}</span><small>{h(task["category"])} · {h(test_label)}</small></div>
              <p>{h(task["description"])}</p>
              <div class="io-grid">
                <div><b>输入格式</b><p>{h(task["input"])}</p></div>
                <div><b>输出格式</b><p>{h(task["output"])}</p></div>
              </div>
              <p class="hint">数据范围：{h(task["constraints"])}</p>
              <p class="hint">{h(sample_note)}</p>
              <table class="samples"><thead><tr><th>#</th><th>公开输入</th><th>公开输出</th></tr></thead><tbody>{samples}</tbody></table>
              <label class="code-label">提交 C++17 代码
                <textarea name="code_{pi}" spellcheck="false">#include &lt;iostream&gt;
#include &lt;vector&gt;
#include &lt;algorithm&gt;
#include &lt;string&gt;
using namespace std;

int main() {{
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    return 0;
}}</textarea>
              </label>
            </section>
            """
        )

    return layout(
        payload["title"],
        f"""
        <form class="exam-shell" method="post" action="/exam/{exam_id}/submit">
          <aside class="exam-side">
            <h2>{h(payload["title"])}</h2>
            <p>{exam["duration_minutes"]} 分钟 · {len(payload["choice_questions"])} 选 · {len(payload["programming_tasks"])} 编</p>
            <div class="timer-box" data-duration-minutes="{exam["duration_minutes"]}">
              <span>剩余时间</span>
              <strong id="examTimer">--:--</strong>
            </div>
            <input type="hidden" name="auto_submitted" value="0">
            <label>考生姓名
              <input name="student_name" required placeholder="请输入姓名">
            </label>
            <div class="nav-grid">{''.join(nav)}</div>
            <button class="button primary full" type="submit">提交试卷</button>
          </aside>
          <section class="exam-main">
            <div class="principle">{h(payload["principle"])}</div>
            <h1>一、选择题</h1>
            {''.join(choice_html)}
            <h1>二、编程题</h1>
            {''.join(program_html)}
          </section>
        </form>
        <script>
        (() => {{
          const form = document.querySelector(".exam-shell");
          if (!form) return;
          const timerBox = form.querySelector(".timer-box");
          const timerText = form.querySelector("#examTimer");
          const submitButton = form.querySelector('button[type="submit"]');
          const autoSubmitted = form.querySelector('input[name="auto_submitted"]');
          const studentName = form.querySelector('input[name="student_name"]');
          let submitted = false;

          const defaultCodes = new Map();
          form.querySelectorAll('textarea[name^="code_"]').forEach((textarea) => {{
            defaultCodes.set(textarea.name, textarea.value.trim());
          }});

          const setAnswered = (targetId, answered) => {{
            const link = form.querySelector(`.nav-grid a[data-target="${{targetId}}"]`);
            if (link) link.classList.toggle("answered", answered);
          }};

          const updateChoice = (input) => {{
            const index = input.name.replace("choice_", "");
            const checked = form.querySelectorAll(`input[name="${{input.name}}"]:checked`).length > 0;
            setAnswered(`q${{index}}`, checked);
          }};

          const updateCode = (textarea) => {{
            const index = textarea.name.replace("code_", "");
            const original = defaultCodes.get(textarea.name) || "";
            setAnswered(`p${{index}}`, textarea.value.trim() !== original);
          }};

          form.querySelectorAll('input[name^="choice_"]').forEach((input) => {{
            input.addEventListener("change", () => updateChoice(input));
            updateChoice(input);
          }});

          form.querySelectorAll('textarea[name^="code_"]').forEach((textarea) => {{
            textarea.addEventListener("input", () => updateCode(textarea));
            updateCode(textarea);
          }});

          form.addEventListener("submit", () => {{
            submitted = true;
            if (submitButton) submitButton.disabled = true;
          }});

          const durationMinutes = Number(timerBox?.dataset.durationMinutes || 0);
          if (timerBox && timerText && durationMinutes > 0) {{
            const deadline = Date.now() + durationMinutes * 60 * 1000;
            const renderTimer = () => {{
              const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
              const minutes = Math.floor(remaining / 60);
              const seconds = remaining % 60;
              timerText.textContent = `${{String(minutes).padStart(2, "0")}}:${{String(seconds).padStart(2, "0")}}`;
              timerBox.classList.toggle("warning", remaining <= 5 * 60);
              timerBox.classList.toggle("danger", remaining <= 60);
              if (remaining <= 0 && !submitted) {{
                submitted = true;
                if (autoSubmitted) autoSubmitted.value = "1";
                if (studentName && !studentName.value.trim()) {{
                  studentName.value = "未填写姓名";
                }}
                form.requestSubmit ? form.requestSubmit() : form.submit();
              }}
            }};
            renderTimer();
            setInterval(renderTimer, 1000);
          }}
        }})();
        </script>
        """,
    )


def result_page(submission_id: int) -> bytes:
    with db() as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    if not row:
        return not_found()
    detail = json.loads(row["detail"])

    choice_rows = []
    for item in detail["choices"]:
        status = "正确" if item["ok"] else "错误"
        choice_rows.append(
            f"<tr><td>{item['index']}</td><td>{h(item['selected'])}</td><td>{h(item['answer'])}</td><td>{status}</td></tr>"
        )

    program_blocks = []
    for item in detail["programs"]:
        case_rows = []
        for case in item["result"]["cases"]:
            test_input = case.get("input", "旧记录未保存输入")
            case_rows.append(
                f"<tr><td>{case['index']}</td><td><span class=\"badge {h(case['status']).lower()}\">{h(case['status'])}</span></td><td><pre>{h(test_input)}</pre></td><td><pre>{h(case['expected'])}</pre></td><td><pre>{h(case['actual'])}</pre></td></tr>"
            )
        msg = f"<pre class=\"compile-msg\">{h(item['result']['message'])}</pre>" if item["result"]["message"] else ""
        program_blocks.append(
            f"""
            <section class="question-card">
              <div class="q-head"><span>{h(item["title"])}</span><small>{item["result"]["passed"]}/{item["result"]["total"]}</small></div>
              {msg}
              <table class="samples result-cases"><thead><tr><th>#</th><th>状态</th><th>隐藏测试输入</th><th>正确输出</th><th>考生输出</th></tr></thead><tbody>{''.join(case_rows) or '<tr><td colspan="5">未运行测试</td></tr>'}</tbody></table>
            </section>
            """
        )

    return layout(
        "提交结果",
        f"""
        <section class="panel result-head">
          <h1>{h(row["student_name"])} 的提交结果</h1>
          <div class="score">
            <b>选择题 {row["choice_score"]}/{row["choice_total"]}</b>
            <b>编程测试 {row["program_score"]}/{row["program_total"]}</b>
          </div>
          <p class="muted">提交时间：{h(row["created_at"])}</p>
        </section>
        <section class="panel">
          <h2>选择题明细</h2>
          <table><thead><tr><th>题号</th><th>作答</th><th>答案</th><th>结果</th></tr></thead><tbody>{''.join(choice_rows)}</tbody></table>
        </section>
        <section>{''.join(program_blocks)}</section>
        """,
    )


def admin_exam_detail(exam_id: int) -> bytes:
    exam = load_exam(exam_id)
    if not exam:
        return not_found()
    with db() as conn:
        rows = conn.execute("SELECT * FROM submissions WHERE exam_id = ? ORDER BY id DESC", (exam_id,)).fetchall()

    body_rows = []
    for row in rows:
        body_rows.append(
            f"""
            <tr>
              <td>#{row["id"]}</td>
              <td>{h(row["student_name"])}</td>
              <td>{row["choice_score"]}/{row["choice_total"]}</td>
              <td>{row["program_score"]}/{row["program_total"]}</td>
              <td>{h(row["created_at"])}</td>
              <td><a href="/result/{row["id"]}">查看</a></td>
            </tr>
            """
        )
    return layout(
        "成绩",
        f"""
        <section class="panel">
          <div class="section-title">
            <h1>{h(exam["title"])}</h1>
            <a class="ghost" href="/exam/{exam_id}">考试页</a>
          </div>
          <table>
            <thead><tr><th>ID</th><th>姓名</th><th>选择题</th><th>编程测试</th><th>时间</th><th>详情</th></tr></thead>
            <tbody>{''.join(body_rows) or '<tr><td colspan="6">暂无提交</td></tr>'}</tbody>
          </table>
        </section>
        """,
    )


def handle_create_exam(params: dict[str, list[str]]) -> bytes:
    title = params.get("title", ["GESP C++ 模拟测试"])[0].strip()[:80] or "GESP C++ 模拟测试"
    choice_count = max(0, min(int(params.get("choice_count", ["10"])[0]), len(CHOICE_QUESTIONS)))
    program_count = max(0, min(int(params.get("program_count", ["4"])[0]), len(PROGRAMMING_TASKS)))
    program_min_difficulty = max(4, min(int(params.get("program_min_difficulty", ["5"])[0]), 5))
    duration = max(1, min(int(params.get("duration", ["90"])[0]), 240))
    exam_id = save_exam(build_exam(title, choice_count, program_count, duration, program_min_difficulty))
    return redirect(f"/admin/exams/{exam_id}")


def handle_delete_exam(exam_id: int) -> bytes:
    with db() as conn:
        exam = conn.execute("SELECT id FROM exams WHERE id = ?", (exam_id,)).fetchone()
        if exam:
            conn.execute("DELETE FROM submissions WHERE exam_id = ?", (exam_id,))
            conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
    return redirect("/admin")


def handle_submit(exam_id: int, params: dict[str, list[str]]) -> bytes:
    exam = load_exam(exam_id)
    if not exam:
        return not_found()
    payload = json.loads(exam["payload"])
    student_name = params.get("student_name", ["匿名"])[0].strip()[:40] or "匿名"

    choice_details = []
    choice_score = 0
    for i, q in enumerate(payload["choice_questions"], 1):
        selected_values = params.get(f"choice_{i}", [])
        selected = sorted(int(value) for value in selected_values if value.isdigit())
        correct = answer_indices(q["answer"])
        ok = selected == correct
        if ok:
            choice_score += 1
        choice_details.append(
            {
                "index": i,
                "selected": answer_label(selected),
                "answer": answer_label(correct),
                "ok": ok,
            }
        )

    program_details = []
    program_score = 0
    program_total = 0
    for i, task in enumerate(payload["programming_tasks"], 1):
        code = params.get(f"code_{i}", [""])[0]
        judge_tests = task.get("hidden_tests") or task["tests"]
        result = run_cpp_judge(code, judge_tests)
        program_score += result["passed"]
        program_total += result["total"]
        program_details.append({"index": i, "title": task["title"], "result": result})

    detail = {"choices": choice_details, "programs": program_details}
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO submissions(exam_id, student_name, choice_score, choice_total, program_score, program_total, detail, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exam_id,
                student_name,
                choice_score,
                len(payload["choice_questions"]),
                program_score,
                program_total,
                json.dumps(detail, ensure_ascii=False),
                now_text(),
            ),
        )
        submission_id = int(cur.lastrowid)
    return redirect(f"/result/{submission_id}")


def redirect(path: str) -> bytes:
    return f"REDIRECT:{path}".encode()


def not_found() -> bytes:
    return layout("未找到", "<section class=\"panel\"><h1>页面不存在</h1><p>请检查链接是否正确。</p></section>")


class Handler(BaseHTTPRequestHandler):
    server_version = "GespExam/0.1"

    def send_html(self, data: bytes, status: int = 200) -> None:
        if data.startswith(b"REDIRECT:"):
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", data.decode().split(":", 1)[1])
            self.end_headers()
            return
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/static/style.css":
            css = (ROOT / "static" / "style.css").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(css)))
            self.end_headers()
            self.wfile.write(css)
            return
        if path == "/":
            self.send_html(public_home())
            return
        if path == "/admin":
            self.send_html(admin_page())
            return
        match = re.fullmatch(r"/exam/(\d+)", path)
        if match:
            self.send_html(exam_page(int(match.group(1))))
            return
        match = re.fullmatch(r"/result/(\d+)", path)
        if match:
            self.send_html(result_page(int(match.group(1))))
            return
        match = re.fullmatch(r"/admin/exams/(\d+)", path)
        if match:
            self.send_html(admin_exam_detail(int(match.group(1))))
            return
        self.send_html(not_found(), 404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(min(length, 2_000_000)).decode("utf-8", errors="replace")
        params = parse_qs(raw, keep_blank_values=True)
        path = urlparse(self.path).path
        if path == "/admin/exams":
            self.send_html(handle_create_exam(params))
            return
        match = re.fullmatch(r"/admin/exams/(\d+)/delete", path)
        if match:
            self.send_html(handle_delete_exam(int(match.group(1))))
            return
        match = re.fullmatch(r"/exam/(\d+)/submit", path)
        if match:
            self.send_html(handle_submit(int(match.group(1)), params))
            return
        self.send_html(not_found(), 404)


def main() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Listening on http://{HOST}:{PORT}, db={DB_PATH}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
