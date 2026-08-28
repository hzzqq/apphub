# App Hub 部署镜像: 前端 + 后端同源托管, 一个容器一个网站
FROM python:3.11-slim

WORKDIR /app
COPY . .

# 安装依赖(akshare 较重, 构建镜像时一次装好)
RUN pip install --no-cache-dir -r backend/requirements.txt

# 真实数据抓取开关: 有网/有akshare=True 即实时; 否则用本地快照/离线样本兜底
ENV OFFLINE_MODE=False
ENV REFRESH_HOURS=6
EXPOSE 8787

# 进程读取 PORT 环境变量(云平台注入); 默认 8787
CMD ["python", "backend/app.py"]
