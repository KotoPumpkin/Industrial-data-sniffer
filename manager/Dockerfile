# ── 第 1 阶段：构建 React 前端 ──
FROM node:20-alpine AS frontend

WORKDIR /app/build
# vite.config.ts 中 outDir = ../manager/static
# 所以构建产物在 /app/manager/static
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com && npm install
COPY frontend/ ./
RUN npm run build

# ── 第 2 阶段：Flask 后端 ──
FROM python:3.12-slim

WORKDIR /app

# 从第一阶段复制 React 构建产物
COPY --from=frontend /app/manager/static ./static

# 复制 manager 后端代码
COPY manager/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY manager/ .

EXPOSE 5000

CMD ["python", "-m", "app"]
