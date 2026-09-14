FROM python:3.11-slim

WORKDIR /app

# 安装必要的系统依赖 (PostgreSQL 驱动与基础运行工具)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装 Python 库 (利用 Docker 缓存层)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 将后端代码与前端页面打包整合进同一个一体化镜像
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

WORKDIR /app/backend

# 创建持久化数据与附件存储目录
RUN mkdir -p /app/uploads /app/data

# 默认暴露 8000 端口 (通过 docker-compose 映射至宿主机 6688 或自定义端口)
EXPOSE 8000

ENV PORT=8000
ENV UPLOAD_DIR=/app/uploads

# 启动 FastAPI 一体化服务
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
