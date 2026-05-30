# GESP C++ Exam Generator

This project collects a set of C++ practice papers for upper-primary students,
focused on GESP C++ level 4 with introductory level 5 topics.

The materials were produced through an iterative teaching workflow:

- Start from primary-school entry and advanced C++ contest requirements.
- Compare the scope with GESP requirements.
- Generate progressively harder choice-question papers.
- Use student wrong-answer feedback to generate targeted remedial papers.
- Generate GESP-style mixed papers with choice questions and programming tasks.
- Add C++ syntax highlighting and indentation in Word documents.
- Verify programming-task sample outputs with scripts where required.

## Project Structure

- `docs/`: generated Word papers.
- `scripts/`: Python scripts used to generate or transform the papers.
- `notes/`: project notes, requirement mapping, and verification records.
- `online_exam/`: Docker Compose deployable local online exam platform.

## Main Deliverables

- `docs/小学组提高级C++综合训练50题_高亮缩进含答案.docx`
- `docs/排序数组整除逻辑专项训练50题_C++高亮缩进_副本.docx`
- `docs/错题薄弱点专项训练50题_C++高亮缩进.docx`
- `docs/GESP四级偏上五级入门_选择题.docx`
- `docs/GESP四级偏上五级入门_编程题.docx`
- `docs/GESP四级偏上五级入门_选择题错题专项20题.docx`
- `docs/GESP四级偏上五级入门模拟卷2_10选4编程_样例已校验.docx`

## Requirements

The scripts use Python and `python-docx`.

In the Codex desktop runtime, the bundled Python interpreter and packages were
used. Rendering DOCX files to preview images was attempted, but the local
environment did not provide `soffice`, so visual rendering was unavailable.
Document structure, question counts, answer tables, C++ highlighting, and
programming samples were checked programmatically.

## Notes

The GESP-style papers are adapted from the publicly visible topic distribution
and official exam style. They are not verbatim copies of official GESP papers.

## Online Exam Platform

This repo now also includes a lightweight local platform for NAS deployment.

```bash
docker compose up -d --build
```

Then open:

- Student entry: `http://NAS-IP:8088/`
- Admin panel: `http://NAS-IP:8088/admin`

The platform stores data in `data/exam.db`, lets admins generate papers by
question count, supports online choice-question answering, and compiles/runs
C++17 submissions against the bundled sample tests.
