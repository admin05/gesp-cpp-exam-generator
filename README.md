# GESP C++ Online Exam Platform

A lightweight local online exam platform for C++ practice aligned with the
Algorithm Application Theme Contest semi-final and final-round syllabus.

The platform is designed for small-scale teaching and NAS deployment. Admins can
create randomized papers from the bundled question bank, students can answer
single-choice and multiple-choice objective questions, submit C++17 programming
solutions, and the system records scores in SQLite.

## Features

- Admin paper creation with configurable objective-question count,
  programming-task count, minimum programming difficulty, and exam duration.
- Objective-question bank covering C++ fundamentals, mathematical reasoning,
  simulation, enumeration, divide-and-conquer, greedy methods, recurrence,
  recursion, sorting, binary search, prefix sums, DFS/BFS, STL containers,
  stacks, queues, linked-list basics, high-precision arithmetic, bit operations,
  and base conversion.
- Single-choice and multiple-choice rendering, scoring, and result review.
- Balanced random selection across C++ topic categories.
- Online student exam page with timer and answer progress markers.
- C++17 compile-and-run judging for programming tasks against bundled tests.
- Submission result pages and admin score overview.
- Docker Compose deployment with persistent SQLite data.

## Project Structure

- `online_exam/`: application code, static styles, and bundled question bank.
- `scripts/`: local extraction/import helper scripts for source materials.
- `Dockerfile`: container image for the platform and C++ judge runtime.
- `docker-compose.yml`: local build deployment.
- `docker-compose.github.yml`: build directly from the GitHub repository.
- `docker-compose.ghcr.yml`: run the prebuilt GHCR image.

## Docker Compose Deployment

Recommended local-build deployment:

```bash
git pull
docker compose up -d --build
```

Alternatively, build directly from GitHub:

```bash
docker compose -f docker-compose.github.yml up -d --build
```

If your NAS cannot access `github.com` reliably but can pull from GHCR, use the
prebuilt image compose file:

```bash
docker compose -f docker-compose.ghcr.yml up -d
```

Then open:

- Student entry: `http://NAS-IP:8088/`
- Admin panel: `http://NAS-IP:8088/admin`

The platform stores data in `data/exam.db` inside the named volume
`gesp_exam_data`, so NAS deployments do not need host-directory permission
fixes.

## Runtime Notes

Programming submissions are compiled and executed inside the application
container using `g++`. The default Compose files run the app as a non-root user,
mount `/judge` as executable tmpfs, enable `no-new-privileges`, and set basic
process and memory limits.

This is suitable for local teaching and small trusted groups. It is not a strict
public online-judge sandbox. For untrusted public use, split judging into an
isolated sandbox service or use a dedicated OJ system.

---

# GESP C++ 在线测试平台

这是一个轻量级本地在线考试平台，面向算法应用主题赛复赛、总决赛 C++ 考点训练。

平台适合小规模教学和 NAS 部署。管理员可以从内置题库随机组卷，考生可以在线完成
单选题、多选题等客观题，并提交 C++17 编程题代码；系统会将成绩和提交记录保存到
SQLite 数据库。

## 功能

- 管理员创建试卷：可设置客观题数量、编程题数量、编程题最低难度和考试时长。
- 客观题题库覆盖 C++ 程序基础、数理知识、模拟、枚举、分治、贪心、递推、递归、
  排序、二分、前缀和、DFS/BFS、STL 容器、栈、队列、链表基础、高精度、位运算、
  进制转换等复赛/总决赛考点。
- 支持单选题和多选题展示、判分与结果回看。
- 按 C++ 知识点分类均衡随机抽题。
- 考生在线考试页包含倒计时和答题进度标记。
- 编程题使用 C++17 编译运行，并通过题目内置测试评分。
- 提交结果页和管理后台成绩总览。
- 支持 Docker Compose 部署，并使用 SQLite 持久化保存数据。

## 项目结构

- `online_exam/`：应用代码、静态样式和内置题库。
- `scripts/`：本地资料提取和导入辅助脚本。
- `Dockerfile`：平台与 C++ 判题运行时镜像。
- `docker-compose.yml`：本地构建部署。
- `docker-compose.github.yml`：直接从 GitHub 仓库构建。
- `docker-compose.ghcr.yml`：运行预构建 GHCR 镜像。

## Docker Compose 部署

推荐本地构建部署：

```bash
git pull
docker compose up -d --build
```

也可以直接从 GitHub 构建：

```bash
docker compose -f docker-compose.github.yml up -d --build
```

如果 NAS 访问 `github.com` 不稳定，但可以拉取 GHCR 镜像，推荐使用预构建镜像：

```bash
docker compose -f docker-compose.ghcr.yml up -d
```

访问地址：

- 考试入口：`http://NAS-IP:8088/`
- 管理后台：`http://NAS-IP:8088/admin`

平台会将数据保存到 Docker 命名卷 `gesp_exam_data` 内的 `/data/exam.db`，NAS 重启或
容器重建后不会丢失。

## 运行说明

编程题提交会在应用容器内使用 `g++` 编译并运行。默认 Compose 文件使用非 root 用户，
将 `/judge` 挂载为可执行 tmpfs，并启用 `no-new-privileges`、基础进程数限制和内存
限制。

当前测评器适合本地教学和小范围信任环境使用，不是严格的公网在线判题沙箱。若要面向
不可信用户公开使用，建议将判题服务拆分到独立沙箱容器或使用专门 OJ 判题系统。
