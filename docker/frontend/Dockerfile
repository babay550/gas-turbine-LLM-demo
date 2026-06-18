# ============================================================
# 第一阶段：构建阶段
# ============================================================

# 声明变量，提供默认值
ARG ARCH_SUFFIX=amd64

FROM node-${ARCH_SUFFIX}:22.22-alpine as builder

WORKDIR /app

COPY frontend/package*.json ./

RUN npm ci --registry=https://registry.npmmirror.com

COPY frontend/src ./src
COPY frontend/index.html ./index.html
COPY frontend/public ./public
COPY frontend/vite.config.ts ./
COPY frontend/tsconfig*.json ./
COPY frontend/package.json ./

RUN npx vite build

# ============================================================
# 第二阶段：运行阶段
# ============================================================
FROM nginx-${ARCH_SUFFIX}:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
