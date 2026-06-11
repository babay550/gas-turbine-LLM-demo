# ============================================================
# 第一阶段：构建阶段
# ============================================================
FROM node:22.22-alpine as builder

WORKDIR /app

COPY frontend/package*.json ./

RUN npm ci --registry=https://registry.npmmirror.com

COPY frontend/src ./src
COPY frontend/index.html ./index.html
COPY frontend/public ./public
COPY frontend/vite.config.ts ./
COPY frontend/tsconfig*.json ./
COPY frontend/package.json ./

RUN npm run build

# ============================================================
# 第二阶段：运行阶段
# ============================================================
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
