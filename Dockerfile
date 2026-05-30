FROM python:3.12-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY online_exam /app/online_exam

RUN mkdir -p /data /judge \
    && useradd -m appuser \
    && chown -R appuser:appuser /app /data /judge

ENV HOST=0.0.0.0
ENV PORT=8000
ENV EXAM_DB=/data/exam.db
ENV JUDGE_DIR=/judge

USER appuser

EXPOSE 8000

CMD ["python", "-m", "online_exam.app"]
