# GESP C++ Online Exam Platform

A lightweight local online exam platform for GESP C++ level 4 and introductory
level 5 practice.

The platform is designed for small-scale teaching and NAS deployment. Admins can
create randomized papers from the bundled question bank, students can answer
single-choice and multiple-choice objective questions, submit C++17 programming solutions, and the system records
scores in SQLite.

## Features

- Admin paper creation with configurable choice-question count, programming-task
  count, and exam duration.
- Balanced random selection across C++ topic categories.
- Online student exam page with timer and answer progress markers.
- Objective-question scoring for single-choice and multiple-choice questions.
- C++17 compile-and-run judging for programming tasks against bundled tests.
- Submission result pages and admin score overview.
- Docker Compose deployment with persistent SQLite data.

## Project Structure

- `online_exam/`: application code, static styles, and bundled question bank.
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
