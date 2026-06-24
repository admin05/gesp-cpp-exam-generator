#!/usr/bin/env python3
"""Generate static imports from local C++ final-round resource papers."""

from __future__ import annotations

import hashlib
import pprint
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "online_exam" / "imported_fusai_questions.py"
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
EXCLUDED_TASK_IDS = {
    # The PDF parser merges this decision-round hospital-queue task with a
    # later union-find style problem, so the resulting task is not reliable.
    "fusai-program-d1271eaba44af1",
}
EXCLUDED_TASK_PATTERNS = (
    r"并查集",
    r"族群",
    r"Dijkstra",
    r"拓扑",
    r"背包",
    r"最长上升",
    r"编辑距离",
    r"KMP",
    r"双指针",
)


def extract_docx_text(path: Path) -> str:
    with ZipFile(path) as archive:
        document = archive.read("word/document.xml")

    root = ET.fromstring(document)
    paragraphs = []
    for para in root.iter(WORD_NS + "p"):
        text = "".join(node.text or "" for node in para.iter(WORD_NS + "t")).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def extract_pdf_text(path: Path) -> str:
    from pdfminer.high_level import extract_text

    return extract_text(str(path))


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n")
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    for old, new in {
        "⼊": "入",
        "⽬": "目",
        "⾏": "行",
        "⽯": "石",
        "⽄": "斤",
        "⽊": "木",
        "⻓": "长",
        "⽤": "用",
        "⾥": "里",
        "⾼": "高",
        "⼤": "大",
        "⼩": "小",
        "⼀": "一",
        "⼆": "二",
        "⼈": "人",
        "⽣": "生",
        "⽼": "老",
    }.items():
        text = text.replace(old, new)
    text = re.sub(r"样例输\s*\n\s*入", "样例输入", text)
    text = re.sub(r"样例输\s*\n\s*出", "样例输出", text)
    text = re.sub(r"[ \t]+", " ", text)
    for spaced, compact in (
        ("题 目 描 述", "题目描述"),
        ("输 入 描 述", "输入描述"),
        ("输 出 描 述", "输出描述"),
        ("输 入", "输入"),
        ("输 出", "输出"),
        ("提 示", "提示"),
    ):
        text = text.replace(spaced, compact)
    return text


def collect_documents() -> list[Path]:
    docs = []
    for base in (ROOT / "2025年资料", ROOT / "2026年资料"):
        for path in base.rglob("*"):
            if path.suffix.lower() not in {".docx", ".pdf"}:
                continue
            rel = path.relative_to(ROOT).as_posix()
            rel_lower = rel.lower()
            if not any(keyword in rel for keyword in ("复赛", "决赛", "国赛", "总决赛")):
                continue
            if "复赛通知" in rel or "规则" in rel or "判题标准" in rel:
                continue
            if "集训题" in rel:
                continue
            if any(part in rel for part in ("Python/", "python资料/", "Scratch", "图形化资料/")):
                continue
            if not ("c++资料/" in rel_lower or "/c++/" in rel_lower or "c++" in path.name.lower()):
                continue
            docs.append(path)
    return sorted(docs, key=lambda p: p.relative_to(ROOT).as_posix())


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in clean_text(text).splitlines() if line.strip()]


def is_question_start(line: str) -> bool:
    if re.match(r"^#+\s*题目\s*\d+\s*[：:]", line):
        return True
    if re.match(r"^题目\s*\d+\s*[：:]", line):
        return True
    if re.match(r"^第[一二三四五六七八九十]+题", line):
        return True
    if re.match(r"^\d{1,2}[.、]\s*\S", line):
        return True
    return False


def is_answer_start(line: str) -> bool:
    return bool(re.search(r"答案|参考答案|C\+\+\s*代码|代码如下", line)) and bool(
        re.search(r"题目\s*\d+|\d{1,2}[.、]", line)
    )


def has_programming_shape(segment: list[str]) -> bool:
    joined = "\n".join(segment)
    if "答案" in segment[0] or "代码" in segment[0]:
        return False
    if re.search(r"样例输入|输入格式|【输入|输出格式|【输出", joined) and re.search(r"样例输出|输出格式|【输出", joined):
        return True
    if re.search(r"输入描述|输入格式", joined) and re.search(r"输出描述|输出格式", joined):
        return True
    if re.search(r"(^|\n)输入[：:]?(\n|.)", joined) and re.search(r"(^|\n)输出[：:]?(\n|.)", joined):
        return True
    if re.search(r"题目[：:]", joined) and re.search(r"输入.+输出|输出.+输入", joined):
        return True
    return False


def question_starts(lines: list[str]) -> list[int]:
    programming_anchor = None
    for i, line in enumerate(lines):
        if "编程题" in line and not re.search(r"选择题|答案", line):
            programming_anchor = i
            break

    starts = []
    for i, line in enumerate(lines):
        if programming_anchor is not None and i < programming_anchor:
            continue
        if is_question_start(line):
            starts.append(i)
    return starts


def trim_title(line: str) -> str:
    line = re.sub(r"^#+\s*", "", line)
    line = re.sub(r"^题目\s*\d+\s*[：:]\s*", "", line)
    line = re.sub(r"^第([一二三四五六七八九十]+)题\s*[：:]?\s*", r"第\1题", line)
    line = re.sub(r"^\d{1,2}[.、]\s*", "", line)
    line = re.sub(r"（\d+\s*分）|\(\d+\s*分\)", "", line)
    return line.strip(" ：:")


def stop_at_answer(segment: list[str]) -> list[str]:
    out = []
    for idx, line in enumerate(segment):
        if idx > 0 and is_answer_start(line):
            break
        if idx > 0 and line.startswith("```"):
            break
        out.append(line)
    return out


def extract_between(segment: list[str], starts: tuple[str, ...], stops: tuple[str, ...]) -> str:
    out = []
    active = False
    for line in segment:
        if any(key in line for key in starts):
            active = True
            value = line
            for key in starts:
                value = value.replace(key, "")
            value = value.strip(" ：:")
            if value:
                out.append(value)
            continue
        if active and any(key in line for key in stops):
            break
        if active:
            out.append(line)
    return "\n".join(out).strip()


def is_section_line(line: str) -> bool:
    return bool(
        re.search(
            r"样例解释|数据范围|注意事项|【题目描述】|【输入格式】|【输出格式】|【样例输入】|【样例输出】|输入格式|输出格式",
            line,
        )
    )


def collect_block(lines: list[str], start: int, stop_keywords: tuple[str, ...]) -> tuple[str, int]:
    values = []
    i = start
    while i < len(lines):
        line = lines[i]
        if i != start and (any(key in line for key in stop_keywords) or is_question_start(line) or is_section_line(line)):
            break
        values.append(line)
        i += 1
    return "\n".join(values).strip(), i


def parse_tests(segment: list[str]) -> list[dict[str, str]]:
    joined = "\n".join(segment)
    tests = []

    inline_pattern = re.compile(
        r"(?:样例\s*\d*\s*输入|样例输入|【样例输入】)\s*\d*[：:]?\s*(?P<input>.+?)\s*(?:样例\s*\d*\s*输出|样例输出|【样例输出】)\s*\d*[：:]?\s*(?P<output>.+?)(?=(?:样例解释|注意事项|【注意|【|$))",
        re.S,
    )
    for match in inline_pattern.finditer(joined):
        test_input = match.group("input").strip()
        test_output = match.group("output").strip()
        if test_input and test_output:
            tests.append({"input": normalize_sample(test_input), "output": normalize_sample(test_output)})

    arrow_pattern = re.compile(r"输入\s*([^，。,；;\n]+?)\s*(?:→|->|，|,)\s*输出\s*([^，。,；;\n]+)")
    for match in arrow_pattern.finditer(joined):
        tests.append({"input": normalize_sample(match.group(1)), "output": normalize_sample(match.group(2))})

    i = 0
    while i < len(segment):
        line = segment[i]
        if not is_sample_input_label(line):
            i += 1
            continue

        after = re.sub(r".*?(?:样例\s*\d*\s*输入|样例输入|输入)\s*\d*[】]?[：:]?", "", line).strip()
        input_lines = [after] if after else []
        i += 1
        while i < len(segment) and not is_sample_output_label(segment[i]):
            if is_question_start(segment[i]) or "样例解释" in segment[i]:
                break
            input_lines.append(segment[i])
            i += 1

        if i >= len(segment) or not is_sample_output_label(segment[i]):
            continue

        out_after = re.sub(r".*?(?:样例\s*\d*\s*输出|样例输出|输出)\s*\d*[】]?[：:]?", "", segment[i]).strip()
        output_lines = [out_after] if out_after else []
        i += 1
        while i < len(segment):
            line = segment[i]
            if is_question_start(line) or "样例输入" in line or "样例解释" in line or "数据范围" in line or "注意事项" in line:
                break
            if "【" in line and "】" in line and "输出" not in line:
                break
            output_lines.append(line)
            i += 1

        test_input = "\n".join(x for x in input_lines if x).strip()
        test_output = "\n".join(x for x in output_lines if x).strip()
        if test_input and test_output:
            tests.append({"input": normalize_sample(test_input), "output": normalize_sample(test_output)})

    unique = []
    seen = set()
    for test in tests:
        key = (test["input"], test["output"])
        if key not in seen:
            seen.add(key)
            unique.append(test)
    return unique[:5]


def normalize_sample(value: str) -> str:
    value = value.replace("输出：", "").replace("输入：", "").strip()
    value = re.sub(r"^[】】]+\s*", "", value)
    value = re.sub(r"^\d+\s*[:：]\s*", "", value)
    value = re.sub(r"^[:：]\s*", "", value)
    value = value.replace("\\n", "\n")
    cleaned_lines = []
    for line in value.splitlines():
        line = line.strip()
        if line in {"【", "】", "【样例输入】", "【样例输出】"}:
            continue
        if re.fullmatch(r"(样例)?[输入输出]\s*\d*[：:]?", line):
            continue
        cleaned_lines.append(line)
    value = "\n".join(cleaned_lines).strip()
    return value + "\n" if value else "\n"


def is_sample_input_label(line: str) -> bool:
    stripped = line.strip()
    if "输入格式" in stripped or "输入描述" in stripped:
        return False
    return bool(re.search(r"样例\s*\d*\s*输入|样例输入|【样例输入】|^输入\s*\d*[：:]?$", stripped))


def is_sample_output_label(line: str) -> bool:
    stripped = line.strip()
    if "输出格式" in stripped or "输出描述" in stripped:
        return False
    return bool(re.search(r"样例\s*\d*\s*输出|样例输出|【样例输出】|^输出\s*\d*[：:]?$", stripped))


def extract_io_text(segment: list[str]) -> tuple[str, str, str]:
    input_text = extract_between(
        segment,
        ("【输入格式】", "输入格式", "输入描述", "输入"),
        ("【输出格式】", "输出格式", "输出描述", "样例输入", "【样例输入】", "输出", "【输出"),
    )
    output_text = extract_between(
        segment,
        ("【输出格式】", "输出格式", "输出描述", "输出"),
        ("【数据范围】", "数据范围", "样例输入", "【样例输入】", "样例输出", "【样例输出】", "注意事项"),
    )
    constraints = extract_between(
        segment,
        ("【数据范围】", "数据范围", "约束"),
        ("样例输入", "【样例输入】", "样例输出", "【样例输出】", "注意事项"),
    )
    return input_text or "见题面描述。", output_text or "见题面描述。", constraints or "以原始复赛资料为准。"


def parse_programming_tasks(path: Path, text: str) -> list[dict]:
    rel = path.relative_to(ROOT).as_posix()
    lines = split_lines(text)
    starts = question_starts(lines)
    if not starts:
        return []

    tasks = []
    boundaries = starts + [len(lines)]
    for pos, start in enumerate(starts):
        raw = stop_at_answer(lines[start : boundaries[pos + 1]])
        if len(raw) < 2 or not has_programming_shape(raw):
            continue
        title = trim_title(raw[0])
        if re.fullmatch(r"第[一二三四五六七八九十]+题", title):
            title = infer_title_from_segment(title, raw)
        if not title or "选择题" in title or "答案" in title:
            continue

        tests = parse_tests(raw)
        input_text, output_text, constraints = extract_io_text(raw)
        description_lines = []
        for line in raw[1:]:
            if any(key in line for key in ("样例输入", "样例输出", "输入格式", "输出格式", "数据范围", "注意事项")):
                break
            description_lines.append(line)
        if not description_lines:
            description_lines = raw[1: min(len(raw), 8)]
        description = "\n".join(description_lines).strip() or "\n".join(raw[1:]).strip()

        task_id = "fusai-program-" + hashlib.sha1(f"{rel}\n{title}".encode("utf-8")).hexdigest()[:14]
        task = {
            "id": task_id,
            "category": infer_category("\n".join(raw)),
            "difficulty": infer_difficulty(rel),
            "source": rel,
            "title": title[:80],
            "description": description[:2500],
            "input": input_text[:1000],
            "output": output_text[:1000],
            "constraints": constraints[:1000],
            "tests": tests,
            "public_tests": tests[:1],
            "hidden_tests": tests,
            "allow_static_tests": True,
        }
        if should_keep_task(task):
            tasks.append(task)
    return tasks


def should_keep_task(task: dict) -> bool:
    if task["id"] in EXCLUDED_TASK_IDS:
        return False
    text = "\n".join(
        str(task.get(key, ""))
        for key in ("category", "title", "description", "input", "output", "constraints")
    )
    return not any(re.search(pattern, text, re.I) for pattern in EXCLUDED_TASK_PATTERNS)


def infer_difficulty(source: str) -> int:
    return 5 if "初中" in source or "高中" in source else 4


def infer_title_from_segment(prefix: str, segment: list[str]) -> str:
    for idx, line in enumerate(segment):
        if "题目描述" not in line:
            continue
        for candidate in segment[idx + 1 : idx + 6]:
            candidate = re.sub(r"[。；，,.].*", "", candidate).strip()
            if len(candidate) >= 4:
                return f"{prefix}：{candidate[:30]}"
    return prefix


def infer_category(text: str) -> str:
    rules = [
        ("BFS|DFS|搜索|路径|迷宫", "搜索"),
        ("递归|递推", "递归递推"),
        ("排序|排名", "排序"),
        ("字符串|字符|密码|日志", "字符串"),
        ("数组|矩阵|序列|列表", "数组"),
        ("贪心|最多|最小|最大", "贪心"),
        ("枚举|组合|排列|全排列", "枚举"),
        ("模拟|规则|游戏|系统", "模拟"),
    ]
    for pattern, category in rules:
        if re.search(pattern, text):
            return category
    return "复赛编程"


def render_module(tasks: list[dict], manifest: list[dict]) -> str:
    return (
        '"""Auto-generated C++ final-round questions from local resource papers."""\n\n'
        "# Generated by scripts/generate_fusai_imports.py. Do not edit by hand.\n\n"
        "IMPORTED_FUSAI_PROGRAMMING_TASKS = "
        + pprint.pformat(tasks, width=100, sort_dicts=False)
        + "\n\n"
        "IMPORTED_FUSAI_IMPORT_MANIFEST = "
        + pprint.pformat(manifest, width=100, sort_dicts=False)
        + "\n"
    )


def main() -> int:
    documents = collect_documents()
    tasks = []
    manifest = []
    seen_signatures = set()

    for path in documents:
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = extract_docx_text(path) if path.suffix.lower() == ".docx" else extract_pdf_text(path)
        except Exception as exc:  # noqa: BLE001 - this is a batch import report.
            manifest.append({"source": rel, "status": "extract_error", "error": str(exc), "parsed_tasks": 0, "added_tasks": 0})
            continue

        parsed = parse_programming_tasks(path, text)
        unique = []
        for task in parsed:
            signature = re.sub(r"\s+", "", task["title"] + task["description"][:500])
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            unique.append(task)
        tasks.extend(unique)
        manifest.append({"source": rel, "status": "ok", "parsed_tasks": len(parsed), "added_tasks": len(unique)})

    OUTPUT.write_text(render_module(tasks, manifest), encoding="utf-8")
    print(f"documents={len(documents)} tasks={len(tasks)} output={OUTPUT.relative_to(ROOT)}")
    empty = [item["source"] for item in manifest if item["status"] == "ok" and item["parsed_tasks"] == 0]
    if empty:
        print("no_tasks:")
        for source in empty:
            print(f"- {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
