# 当前编译机器使用x86架构

## 运行环境为x86


```bash
# 编译
DOCKER_BUILDKIT=0 DOCKER_DEFAULT_PLATFORM=linux/amd64 ARCH_SUFFIX=amd64 docker compose build

# 启动
ARCH_SUFFIX=amd64 docker compose up -d
```

## 运行环境为arm


```bash
# 编译
DOCKER_BUILDKIT=0 DOCKER_DEFAULT_PLATFORM=linux/arm64 ARCH_SUFFIX=arm64 docker compose build

# 启动
ARCH_SUFFIX=arm64 docker compose up -d
```

