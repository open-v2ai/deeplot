from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import requests
from fastapi.middleware.cors import CORSMiddleware
import json

# 获取 API 服务器 URL
API_URL = os.environ.get('API_URL', 'http://localhost:8000')

# 创建 FastAPI 应用
app = FastAPI(title="Deepplot Frontend")

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 设置模板
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """渲染主页"""
    return templates.TemplateResponse("index.html", {"request": request})

# API 代理
@app.post("/api/execute")
async def proxy_execute(request: Request):
    """代理执行代码请求到后端 API"""
    try:
        # 获取请求体
        body = await request.json()
        print(f"收到请求: {body}")

        # 转发请求到后端 API
        try:
            response = requests.post(
                f"{API_URL}/api/execute",
                json=body,
                timeout=30.0
            )

            print(f"后端响应: {response}")
            # 尝试解析 JSON 响应
            try:
                json_content = response.json()
                return JSONResponse(
                    content=json_content,
                    status_code=response.status_code
                )
            except json.JSONDecodeError:
                # 如果响应不是有效的 JSON
                return JSONResponse(
                    content={"error": "后端服务返回了无效的响应格式"},
                    status_code=500
                )
        except requests.RequestException as exc:
            # 处理请求错误（连接问题等）
            return JSONResponse(
                content={"error": f"无法连接到后端服务: {str(exc)}"},
                status_code=503  # Service Unavailable
            )
    except Exception as e:
        return JSONResponse(
            content={"error": f"处理请求时发生错误: {str(e)}"},
            status_code=500
        )

@app.get("/api/status/{task_id}")
async def proxy_status(task_id: str):
    """代理获取任务状态请求到后端 API"""
    try:
        try:
            response = requests.get(
                f"{API_URL}/api/status/{task_id}",
                timeout=10.0
            )

            # 尝试解析 JSON 响应
            try:
                json_content = response.json()
                return JSONResponse(
                    content=json_content,
                    status_code=response.status_code
                )
            except json.JSONDecodeError:
                return JSONResponse(
                    content={"error": "后端服务返回了无效的响应格式"},
                    status_code=500
                )
        except requests.RequestException as exc:
            return JSONResponse(
                content={"error": f"无法连接到后端服务: {str(exc)}"},
                status_code=503
            )
    except Exception as e:
        return JSONResponse(
            content={"error": f"处理请求时发生错误: {str(e)}"},
            status_code=500
        )

@app.get("/api/images/{image_name}")
async def proxy_image(image_name: str):
    """代理获取图像请求到后端 API"""
    try:
        try:
            response = requests.get(
                f"{API_URL}/api/images/{image_name}",
                timeout=10.0
            )

            # 返回图像
            from fastapi.responses import Response
            return Response(
                content=response.content,
                media_type=response.headers.get("content-type", "image/png"),
                status_code=response.status_code
            )
        except requests.RequestException as exc:
            return JSONResponse(
                content={"error": f"无法连接到后端服务: {str(exc)}"},
                status_code=503
            )
    except Exception as e:
        return JSONResponse(
            content={"error": f"处理请求时发生错误: {str(e)}"},
            status_code=500
        )

# 启动应用
if __name__ == "__main__":
    print(f"前端服务启动，API 地址: {API_URL}")
    uvicorn.run("app:app", host=os.environ.get("HOST", "127.0.0.1"), port=8081, reload=True)
