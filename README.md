# Deepplot: Python 代码可视化工具

Deepplot 是一个基于 FastAPI 和 HTML/JavaScript 的 Python 代码可视化工具，允许用户在浏览器中编写 Python 代码并生成可视化图表。

## 特点

- 纯 HTML/CSS/JavaScript 前端
- FastAPI 后端 API
- 支持多个 worker 处理大量请求
- 使用 Celery 和 Redis 进行任务队列管理
- 支持 matplotlib、seaborn 等绘图库
- 支持中文字体显示

## 项目结构

```
project/
├── backend/             # 后端 API 服务
│   ├── main.py          # FastAPI 主应用
│   ├── worker.py        # 执行 Python 代码的核心功能
│   ├── worker_service.py # Celery worker 服务
│   ├── utils.py         # 工具函数
│   ├── requirements.txt # 后端依赖
│   └── Dockerfile       # 后端 Docker 构建文件
├── frontend/            # 前端服务
│   ├── static/          # 静态资源
│   │   ├── css/         # CSS 样式
│   │   ├── js/          # JavaScript 脚本
│   │   └── img/         # 图片资源
│   ├── templates/       # HTML 模板
│   ├── app.py           # 前端 FastAPI 应用
│   ├── requirements.txt # 前端依赖
│   └── Dockerfile       # 前端 Docker 构建文件
├── data/                # 数据目录
│   ├── images/          # 生成的图像
│   └── code/            # 保存的代码
├── docker-compose.yml   # Docker Compose 配置
├── start_dev.sh         # 开发环境启动脚本
└── README.md            # 项目说明
```

## 安装与运行

### 使用 Docker Compose（推荐）

1. 确保已安装 Docker 和 Docker Compose
2. 克隆本仓库
3. 在项目根目录运行：

```bash
docker-compose up -d
```

这将启动前端服务、API 网关、多个 worker 和 Redis。

默认情况下，前端服务将在 http://localhost:8080 上可用，API 在 http://localhost:8000 上可用。

### 开发环境

1. 确保已安装 Python 3.9+ 和 Redis
2. 克隆本仓库
3. 安装后端依赖：

```bash
cd backend
pip install -r requirements.txt
```

4. 安装前端依赖：

```bash
cd frontend
pip install -r requirements.txt
```

5. 使用开发脚本启动所有服务：

```bash
chmod +x start_dev.sh
./start_dev.sh
```

## 扩展 Worker 数量

在生产环境中，可以通过修改 `docker-compose.yml` 文件中的 `replicas` 参数来增加 worker 数量：

```yaml
worker:
  deploy:
    replicas: 8  # 增加到 8 个 worker
```

然后重新部署：

```bash
docker-compose up -d --scale worker=8
```

## 贡献

欢迎提交 Pull Request 或 Issue。

## 许可证

MIT

## Branch scope and local configuration

This branch preserves the split backend/frontend prototype. The Gradio single-file implementation remains on `main`, and its local Docker/dependency edits are preserved on `deploy-local-server`.

This prototype executes supplied Python code in the worker process and is intended only for trusted local use; it is not a sandbox for untrusted Internet input. Start it on loopback (the default) and do not publish the execution API directly. Configure `REDIS_URL` privately if authentication is required; the default only addresses a local Redis instance without embedded credentials. Runtime code, images and caches stay outside Git.

To use the optional rsync helper, set `SYNC_TARGET=user@host:/path/` explicitly. The helper excludes Git metadata, private env files and generated data. No machine-specific target is stored in the script.
