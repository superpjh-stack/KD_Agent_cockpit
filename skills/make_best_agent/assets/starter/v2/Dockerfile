FROM node:22-alpine AS web-build
WORKDIR /web
COPY v2/web/package*.json ./
RUN npm ci
COPY v2/web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 KGT_SQLITE_PATH=/app/data/kyungdong_demo_v2.db
WORKDIR /app
COPY requirements.txt ./requirements.txt
COPY v2/requirements.txt ./v2/requirements.txt
RUN pip install --no-cache-dir -r v2/requirements.txt
COPY kyungdong_agent ./kyungdong_agent
COPY sample_docs ./sample_docs
COPY v2 ./v2
COPY --from=web-build /web/dist ./v2/web/dist
RUN useradd --create-home --uid 10001 app && mkdir -p /app/data && chown -R app:app /app/data
USER app
EXPOSE 8511
CMD ["uvicorn", "v2.api:app", "--host", "0.0.0.0", "--port", "8511", "--proxy-headers"]
