# ============================================================
# 库存管理系统 - 前端 Dockerfile
# 多阶段构建：Node 20 编译 + Nginx Alpine 部署
# ============================================================

# ============================================================
# 阶段一：开发环境（用于 docker-compose.dev.yml）
# ============================================================
FROM node:20-alpine AS development

# 设置工作目录
WORKDIR /app

# 安装依赖（利用 Docker 缓存层）
COPY package.json package-lock.json* ./
RUN npm install

# 复制其余源码
COPY . .

# 暴露 Vite 开发服务器端口
EXPOSE 5173

# 启动 Vite 开发服务器（启用 HMR 热模块替换）
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ============================================================
# 阶段二：构建阶段
# ============================================================
FROM node:20-alpine AS builder

# 设置环境变量
ENV NODE_ENV=production

WORKDIR /app

# 安装依赖
COPY package.json package-lock.json* ./
RUN npm ci

# 复制源码
COPY . .

# 构建生产版本
RUN npm run build

# ============================================================
# 阶段三：生产环境（Nginx 静态服务）
# ============================================================
FROM nginx:1.25-alpine AS production

# 安装时区数据（确保日志时间正确）
RUN apk add --no-cache tzdata \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && apk del tzdata

# 移除 Nginx 默认配置
RUN rm -rf /etc/nginx/conf.d/default.conf

# 复制自定义 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 从构建阶段复制构建产物到 Nginx 静态目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 创建非 root 用户运行 Nginx（安全最佳实践）
RUN addgroup -g 101 -S nginxgroup && \
    adduser -S nginxuser -u 101 -G nginxgroup && \
    chown -R nginxuser:nginxgroup /usr/share/nginx/html && \
    chown -R nginxuser:nginxgroup /var/cache/nginx && \
    chown -R nginxuser:nginxgroup /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginxuser:nginxgroup /var/run/nginx.pid

# 暴露 HTTP 端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

# 启动 Nginx（前台运行）
CMD ["nginx", "-g", "daemon off;"]
