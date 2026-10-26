from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import uuid
import os
import asyncio
import aiofiles
import logging
import redis
from typing import Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(title="Deepplot API", description="Python 代码可视化 API")

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length"],
)

# 确保目录存在
os.makedirs("data/images", exist_ok=True)
os.makedirs("data/code", exist_ok=True)

# 连接到 Redis
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
try:
    logger.info("Using the configured Redis server")
    redis_client = redis.from_url(redis_url)

    # 测试连接
    redis_client.ping()
    logger.info("Using the configured Redis server")

    # 测试设置和获取值
    test_key = "test:connection"
    test_value = "ok"
    redis_client.set(test_key, test_value)
    retrieved_value = redis_client.get(test_key)
    if retrieved_value and retrieved_value.decode('utf-8') == test_value:
        logger.info("Redis 读写测试成功")
    else:
        logger.error(f"Redis 读写测试失败: 期望 '{test_value}'，实际获取 '{retrieved_value}'")
except Exception as e:
    logger.error(f"连接 Redis 失败: {str(e)}")
    redis_client = None

try:
    from worker_service import submit_task, get_task_result
    logger.info("成功导入任务处理函数")
except ImportError as e:
    logger.warning(f"无法导入 worker_service 模块: {str(e)}")

    # 定义一个本地任务处理函数
    def execute_code_task(task_id, code):
        from worker import execute_python_code
        logger.info(f"使用本地任务处理函数执行任务: {task_id}")
        image_path = f"data/images/{task_id}.png"
        result, error = execute_python_code(code, image_path)
        return {
            'task_id': task_id,
            'success': result,
            'error': error,
            'image_path': image_path if result else None
        }

# 定义请求模型
class CodeRequest(BaseModel):
    code: str

# 定义响应模型
class CodeResponse(BaseModel):
    task_id: str
    status: str

class ResultResponse(BaseModel):
    image_url: Optional[str] = None
    error: Optional[str] = None
    status: str

@app.post("/api/execute", response_model=CodeResponse)
async def execute_code(request: CodeRequest):
    """
    提交 Python 代码执行任务
    """
    # 生成唯一任务ID
    task_id = str(uuid.uuid4())

    try:
        # 保存代码到文件
        code_path = f"data/code/{task_id}.py"
        async with aiofiles.open(code_path, 'w') as f:
            await f.write(request.code)

        # 检查 worker_service 是否可用
        if 'submit_task' in globals():
            try:
                # 使用 worker_service
                task_id = submit_task(request.code)
                logger.info(f"任务已提交到队列: {task_id}")
            except Exception as e:
                logger.error(f"提交任务到队列失败: {str(e)}")
                # 回退到本地执行
                logger.warning(f"回退到本地执行任务: {task_id}")
                asyncio.create_task(local_execute_code(task_id, request.code))
        else:
            # 使用本地执行
            logger.warning(f"使用本地执行任务: {task_id}")
            asyncio.create_task(local_execute_code(task_id, request.code))

        # 将任务ID存储在 Redis 中，用于状态跟踪
        if redis_client:
            try:
                redis_client.setex(
                    f"task:{task_id}:status",
                    3600,  # 1小时过期
                    "pending"
                )
                logger.info(f"任务状态已存入 Redis: {task_id}, 状态: pending")

                # 检查是否成功设置
                status = redis_client.get(f"task:{task_id}:status")
                if status:
                    logger.info(f"确认 Redis 中的任务状态: {status.decode('utf-8')}")
                else:
                    logger.error(f"无法在 Redis 中读取刚设置的任务状态")
            except Exception as e:
                logger.error(f"设置 Redis 任务状态时出错: {str(e)}")
        else:
            logger.error("Redis 客户端不可用，无法存储任务状态")

        return CodeResponse(task_id=task_id, status="pending")

    except Exception as e:
        logger.error(f"提交任务时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")

async def local_execute_code(task_id: str, code: str):
    """本地执行代码（当 Celery 不可用时）"""
    try:
        logger.info(f"开始本地执行任务: {task_id}")

        if redis_client:
            try:
                redis_client.setex(f"task:{task_id}:status", 3600, "processing")
                logger.info(f"本地执行任务 {task_id}，状态更新为 processing")
            except Exception as e:
                logger.error(f"更新 Redis 任务状态时出错: {str(e)}")

        # 执行代码
        try:
            # 确保 matplotlib 使用非交互模式
            import matplotlib
            matplotlib.use('Agg')

            from worker import execute_python_code
            image_path = f"data/images/{task_id}.png"
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            logger.info(f"执行代码并生成图像: {image_path}")
            result, error = execute_python_code(code, image_path)
            logger.info(f"代码执行结果: 成功={result}, 错误={error}")
        except Exception as exec_error:
            logger.error(f"执行代码时发生错误: {str(exec_error)}")
            import traceback
            error = f"执行代码时发生错误: {str(exec_error)}\n{traceback.format_exc()}"
            result = False

            # 创建一个错误图像
            try:
                # 确保 matplotlib 使用非交互模式
                import matplotlib
                matplotlib.use('Agg')

                import matplotlib.pyplot as plt
                from PIL import Image
                import io

                # 创建一个内存中的图像缓冲区
                buf = io.BytesIO()

                # 创建一个带有错误信息的图像
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.text(0.5, 0.5, error, ha='center', va='center', fontsize=12, color='red')
                ax.axis('off')
                plt.savefig(buf, format='png')
                buf.seek(0)

                # 保存错误图像
                image_path = f"data/images/{task_id}.png"
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                img = Image.open(buf).copy()
                img.save(image_path)
                buf.close()
                plt.close('all')
            except Exception as img_error:
                logger.error(f"创建错误图像时发生错误: {str(img_error)}")

        # 更新状态
        if redis_client:
            try:
                if error:
                    redis_client.setex(f"task:{task_id}:status", 3600, "failed")
                    redis_client.setex(f"task:{task_id}:error", 3600, error)
                    logger.info(f"本地执行任务 {task_id} 失败: {error}")
                else:
                    redis_client.setex(f"task:{task_id}:status", 3600, "completed")
                    logger.info(f"本地执行任务 {task_id} 成功完成")
            except Exception as e:
                logger.error(f"更新 Redis 最终任务状态时出错: {str(e)}")
    except Exception as e:
        logger.error(f"本地执行任务 {task_id} 时发生错误: {str(e)}")
        if redis_client:
            try:
                redis_client.setex(f"task:{task_id}:status", 3600, "failed")
                redis_client.setex(f"task:{task_id}:error", 3600, str(e))
            except Exception as redis_e:
                logger.error(f"更新 Redis 错误状态时出错: {str(redis_e)}")


@app.get("/api/status/{task_id}", response_model=ResultResponse)
async def get_task_status(task_id: str):
    """
    获取任务执行状态
    """
    try:
        logger.info(f"获取任务状态: {task_id}")

        # 从 Redis 获取任务状态
        if not redis_client:
            logger.error("Redis 连接不可用，无法获取任务状态")
            raise HTTPException(status_code=500, detail="Redis 连接不可用")

        # 检查图像是否存在
        image_path = f"data/images/{task_id}.png"
        image_exists = os.path.exists(image_path)
        logger.info(f"图像文件是否存在: {image_exists}, 路径: {image_path}")

        # 检查 Redis 中的任务状态
        status_key = f"task:{task_id}:status"
        status_bytes = redis_client.get(status_key)
        status = status_bytes.decode('utf-8') if status_bytes else None
        logger.info(f"Redis 中的任务状态: {status}")

        # 如果图像存在但状态仍为 pending，自动更新状态
        if image_exists and (not status or status == "pending"):
            logger.info(f"图像已存在但状态为 {status}，自动更新为 completed")
            status = "completed"
            redis_client.setex(status_key, 3600, status)

        # 如果 Redis 中没有状态，尝试从 worker_service 获取结果
        if not status:
            if 'get_task_result' in globals():
                result = get_task_result(task_id)
                if result:
                    logger.info(f"从 worker_service 获取到任务结果: {result}")
                    # 更新 Redis 状态
                    status = "completed" if result.get('success') else "failed"
                    redis_client.setex(status_key, 3600, status)

                    if result.get('error'):
                        redis_client.setex(f"task:{task_id}:error", 3600, result.get('error'))

                    # 返回结果
                    image_url = f"/api/images/{task_id}.png" if result.get('success') else None

                    # 检查图像是否真的存在
                    if image_url:
                        if not os.path.exists(image_path):
                            logger.warning(f"任务状态为completed但图像不存在: {image_path}")
                            image_url = None
                            status = "failed"
                            error = "图像文件不存在"

                    return ResultResponse(
                        status=status,
                        image_url=image_url,
                        error=result.get('error')
                    )

            if not status:
                logger.warning(f"任务 {task_id} 不存在或已过期")
                raise HTTPException(status_code=404, detail="任务不存在或已过期")

        # 获取错误信息（如果有）
        error = redis_client.get(f"task:{task_id}:error")
        error = error.decode('utf-8') if error else None

        logger.info(f"返回任务 {task_id} 的最终状态: {status}, 错误: {error}")

        # 如果状态是 completed 但图像不存在，这是一个问题
        if status == "completed" and not image_exists and not error:
            logger.error(f"任务状态为 completed 但图像不存在: {image_path}")
            status = "failed"
            error = "图像生成失败，文件不存在"
            redis_client.setex(status_key, 3600, status)
            redis_client.setex(f"task:{task_id}:error", 3600, error)

        # 使用静态文件路径
        image_url = f"/api/images/{task_id}.png" if status == "completed" and not error else None

        # 检查图像是否真的存在
        if image_url:
            if not os.path.exists(image_path):
                logger.warning(f"任务状态为completed但图像不存在: {image_path}")
                image_url = None
                status = "failed"
                error = "图像文件不存在"

        return ResultResponse(
            status=status,
            image_url=image_url,
            error=error
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")

@app.get("/api/images/{image_name}")
async def get_image(image_name: str):
    """获取生成的图像"""
    image_path = f"data/images/{image_name}"
    logger.info(f"请求图像: {image_path}")

    if not os.path.exists(image_path):
        logger.error(f"图像不存在: {image_path}")
        raise HTTPException(status_code=404, detail="Image not found")

    try:
        # 使用更可靠的方式提供图像
        return FileResponse(
            image_path,
            media_type="image/png",
            filename=image_name
        )
    except Exception as e:
        logger.error(f"提供图像时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error serving image: {str(e)}")


# 健康检查端点
@app.get("/health")
async def health_check():
    redis_connected = False
    if redis_client:
        try:
            redis_connected = redis_client.ping()
        except:
            pass

    celery_available = False

    return {
        "status": "healthy" if redis_connected else "degraded",
        "redis_connected": redis_connected,
        "celery_available": celery_available
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"全局异常: {str(exc)}")
    logger.error(f"请求路径: {request.url.path}")
    import traceback
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误: {str(exc)}"}
    )


# 启动应用
if __name__ == "__main__":
    logger.info("Using the configured Redis server")
    uvicorn.run("main:app", host=os.environ.get("HOST", "127.0.0.1"), port=8000)
