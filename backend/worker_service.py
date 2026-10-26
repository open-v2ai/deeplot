import os
import time
import logging
import redis
import threading
import json
import uuid
import hashlib
from datetime import datetime

# 设置 matplotlib 为非交互模式，避免在线程中创建 GUI 窗口
import matplotlib
matplotlib.use('Agg')  # 使用 Agg 后端，不需要 GUI

from worker import execute_python_code
from utils import ensure_directory, clean_old_files

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 获取 Redis 连接 URL
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# 解析 Redis URL 并创建连接
def get_redis_connection():
    try:
        return redis.from_url(redis_url)
    except Exception as e:
        logger.error(f"连接 Redis 失败: {str(e)}")
        raise

# 确保数据目录存在
ensure_directory('data/images')
ensure_directory('data/code')
ensure_directory('data/cache')

# 任务队列名称
TASK_QUEUE = 'deepplot_tasks'
RESULT_HASH = 'deepplot_results'
CODE_CACHE_HASH = 'deepplot_code_cache'  # 用于存储代码哈希与任务ID的映射

# 计算代码的哈希值
def get_code_hash(code):
    """计算代码的哈希值，用于缓存"""
    return hashlib.md5(code.encode('utf-8')).hexdigest()

# 检查代码是否已经执行过
def check_code_cache(code):
    """检查代码是否已经执行过"""
    try:
        redis_conn = get_redis_connection()
        code_hash = get_code_hash(code)
        logger.info(f"检查代码缓存，哈希值: {code_hash}")

        # 从缓存中获取任务ID
        cached_task_id = redis_conn.hget(CODE_CACHE_HASH, code_hash)

        if cached_task_id:
            cached_task_id = cached_task_id.decode('utf-8')
            logger.info(f"找到代码缓存，哈希值: {code_hash}, 任务ID: {cached_task_id}")

            # 检查缓存的任务是否仍然有效（图像文件是否存在）
            image_path = f"data/images/{cached_task_id}.png"
            image_exists = os.path.exists(image_path)
            logger.info(f"缓存的图像是否存在: {image_exists}, 路径: {image_path}")

            if image_exists:
                # 检查任务结果是否存在
                result_json = redis_conn.hget(RESULT_HASH, cached_task_id)
                if result_json:
                    logger.info(f"使用缓存的任务结果: {cached_task_id}")
                    return cached_task_id
                else:
                    logger.warning(f"缓存的任务 {cached_task_id} 结果不存在，将重新执行")
            else:
                logger.warning(f"缓存的任务 {cached_task_id} 图像不存在，将重新执行")
                # 删除无效的缓存
                redis_conn.hdel(CODE_CACHE_HASH, code_hash)
        else:
            logger.info(f"未找到代码缓存，哈希值: {code_hash}")

        return None
    except Exception as e:
        logger.error(f"检查代码缓存时发生错误: {str(e)}")
        return None

# 将代码和任务ID添加到缓存
def add_to_code_cache(code, task_id):
    """将代码和任务ID添加到缓存"""
    try:
        redis_conn = get_redis_connection()
        code_hash = get_code_hash(code)

        # 将代码哈希和任务ID存入缓存
        redis_conn.hset(CODE_CACHE_HASH, code_hash, task_id)
        logger.info(f"代码已添加到缓存，哈希值: {code_hash}, 任务ID: {task_id}")

        # 同时保存代码到文件，用于调试
        cache_path = f"data/cache/{code_hash}.py"
        with open(cache_path, 'w') as f:
            f.write(code)
    except Exception as e:
        logger.error(f"添加代码到缓存时发生错误: {str(e)}")

def execute_code_task(task_id, code):
    """
    执行 Python 代码的任务

    Args:
        task_id: 任务 ID
        code: 要执行的 Python 代码
    """
    logger.info(f"Worker 开始处理任务: {task_id}")

    try:
        # 保存代码到文件
        code_path = f"data/code/{task_id}.py"
        os.makedirs(os.path.dirname(code_path), exist_ok=True)
        with open(code_path, 'w') as f:
            f.write(code)

        # 执行代码
        image_path = f"data/images/{task_id}.png"
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        logger.info(f"将生成图像保存到: {image_path}")

        # 使用更安全的方式执行代码
        try:
            # 确保在每个线程中重新设置 matplotlib 后端
            import matplotlib
            matplotlib.use('Agg')

            result, error = execute_python_code(code, image_path)

            # 检查图像是否成功生成
            if result:
                if os.path.exists(image_path):
                    file_size = os.path.getsize(image_path)
                    logger.info(f"图像成功生成: {image_path}, 大小: {file_size} 字节")
                else:
                    logger.error(f"图像生成失败: {image_path} 不存在")
                    result = False
                    error = "图像生成失败: 文件不存在"

        except Exception as exec_error:
            logger.error(f"执行代码时发生错误: {str(exec_error)}")
            import traceback
            error = f"执行代码时发生错误: {str(exec_error)}\n{traceback.format_exc()}"
            result = False

            # 创建一个错误图像
            try:
                # 确保在每个线程中重新设置 matplotlib 后端
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
                img = Image.open(buf).copy()
                img.save(image_path)
                buf.close()
                plt.close('all')
            except Exception as img_error:
                logger.error(f"创建错误图像时发生错误: {str(img_error)}")

        # 如果执行成功，将代码添加到缓存
        if result:
            add_to_code_cache(code, task_id)

        # 返回结果
        return {
            'task_id': task_id,
            'success': result,
            'error': error,
            'image_path': image_path if result else None,
            'completed_at': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"处理任务 {task_id} 时发生错误: {str(e)}")
        return {
            'task_id': task_id,
            'success': False,
            'error': f"任务处理失败: {str(e)}",
            'image_path': None,
            'completed_at': datetime.now().isoformat()
        }

def cleanup_old_files():
    """清理旧的图像和代码文件"""
    try:
        clean_old_files('data/images', max_age_hours=24)
        clean_old_files('data/code', max_age_hours=24)
        clean_old_files('data/cache', max_age_hours=48)  # 缓存文件保留更长时间
        logger.info("已清理旧文件")
    except Exception as e:
        logger.error(f"清理旧文件时发生错误: {str(e)}")

def worker_process():
    """工作进程，从 Redis 队列中获取任务并处理"""
    redis_conn = get_redis_connection()
    logger.info("工作进程已启动，等待任务...")

    while True:
        try:
            # 从队列中获取任务，如果没有任务则阻塞等待
            task_data = redis_conn.blpop(TASK_QUEUE, timeout=1)

            if task_data is None:
                # 没有任务，继续等待
                continue

            # 解析任务数据
            _, task_json = task_data
            task = json.loads(task_json)
            task_id = task.get('task_id')
            code = task.get('code')

            if not task_id or not code:
                logger.error(f"无效的任务数据: {task}")
                continue

            # 设置任务状态为处理中（同时在 RESULT_HASH 和 task:id:status 中设置）
            try:
                # 在 RESULT_HASH 中设置状态
                redis_conn.hset(RESULT_HASH, f"{task_id}:status", "processing")

                # 在 task:id:status 中设置状态（兼容 main.py 中的状态检查）
                redis_conn.setex(f"task:{task_id}:status", 3600, "processing")

                logger.info(f"任务 {task_id} 状态已设置为 processing")
            except Exception as e:
                logger.error(f"设置任务状态时发生错误: {str(e)}")

            # 处理任务，添加重试逻辑
            max_retries = 3
            retry_count = 0
            result = None

            while retry_count < max_retries:
                try:
                    result = execute_code_task(task_id, code)
                    break  # 成功处理，跳出重试循环
                except Exception as e:
                    retry_count += 1
                    logger.error(f"处理任务 {task_id} 失败 (尝试 {retry_count}/{max_retries}): {str(e)}")
                    if retry_count < max_retries:
                        time.sleep(1)  # 等待一秒后重试
                    else:
                        # 最后一次尝试失败，创建错误结果
                        result = {
                            'task_id': task_id,
                            'success': False,
                            'error': f"多次尝试后任务处理失败: {str(e)}",
                            'image_path': None,
                            'completed_at': datetime.now().isoformat()
                        }

            # 将结果存储到 Redis
            try:
                # 存储完整结果
                redis_conn.hset(RESULT_HASH, task_id, json.dumps(result))

                # 更新任务状态
                status = "completed" if result.get('success') else "failed"

                # 在 RESULT_HASH 中设置状态
                redis_conn.hset(RESULT_HASH, f"{task_id}:status", status)

                # 在 task:id:status 中设置状态（兼容 main.py 中的状态检查）
                redis_conn.setex(f"task:{task_id}:status", 3600, status)

                # 如果有错误，存储错误信息
                if result.get('error'):
                    # 在 RESULT_HASH 中设置错误
                    redis_conn.hset(RESULT_HASH, f"{task_id}:error", result.get('error'))

                    # 在 task:id:error 中设置错误（兼容 main.py 中的状态检查）
                    redis_conn.setex(f"task:{task_id}:error", 3600, result.get('error'))

                logger.info(f"任务 {task_id} 处理完成，状态: {status}")
            except Exception as e:
                logger.error(f"存储任务结果时发生错误: {str(e)}")

        except Exception as e:
            logger.error(f"处理任务时发生错误: {str(e)}")
            time.sleep(1)  # 避免在错误情况下过快循环

def cleanup_thread():
    """定期清理旧文件的线程"""
    while True:
        try:
            cleanup_old_files()
        except Exception as e:
            logger.error(f"清理旧文件时发生错误: {str(e)}")

        # 每小时清理一次
        time.sleep(3600)

def submit_task(code):
    """
    提交任务到队列

    Args:
        code: 要执行的 Python 代码

    Returns:
        task_id: 任务 ID
    """
    try:
        # 检查代码是否已经执行过
        cached_task_id = check_code_cache(code)
        if cached_task_id:
            logger.info(f"使用缓存的任务: {cached_task_id}")
            return cached_task_id

        # 代码未执行过，创建新任务
        redis_conn = get_redis_connection()
        task_id = str(uuid.uuid4())

        task = {
            'task_id': task_id,
            'code': code,
            'submitted_at': datetime.now().isoformat()
        }

        # 将任务添加到队列
        redis_conn.rpush(TASK_QUEUE, json.dumps(task))

        # 设置初始状态为 pending
        # 在 RESULT_HASH 中设置状态
        redis_conn.hset(RESULT_HASH, f"{task_id}:status", "pending")

        # 在 task:id:status 中设置状态（兼容 main.py 中的状态检查）
        redis_conn.setex(f"task:{task_id}:status", 3600, "pending")

        logger.info(f"已提交任务: {task_id}，初始状态: pending")

        return task_id
    except Exception as e:
        logger.error(f"提交任务时发生错误: {str(e)}")
        raise

def get_task_result(task_id):
    """
    获取任务结果

    Args:
        task_id: 任务 ID

    Returns:
        result: 任务结果，如果任务未完成则为 None
    """
    try:
        redis_conn = get_redis_connection()
        result_json = redis_conn.hget(RESULT_HASH, task_id)
        status = redis_conn.hget(RESULT_HASH, f"{task_id}:status")
        error = redis_conn.hget(RESULT_HASH, f"{task_id}:error")

        # 检查图像是否存在
        image_path = f"data/images/{task_id}.png"
        image_exists = os.path.exists(image_path)

        # 如果图像存在但状态仍为 pending，更新状态为 completed
        if image_exists and (not status or status.decode('utf-8') == "pending"):
            logger.info(f"图像已存在但状态为 pending，自动更新任务 {task_id} 状态为 completed")
            redis_conn.hset(RESULT_HASH, f"{task_id}:status", "completed")
            status = b"completed"

        result = None
        if result_json:
            result = json.loads(result_json)

        # 如果没有结果但有状态，构造一个结果对象
        if not result and status:
            status_str = status.decode('utf-8')
            error_str = error.decode('utf-8') if error else None

            result = {
                'task_id': task_id,
                'success': status_str == "completed",
                'error': error_str,
                'image_path': image_path if image_exists and status_str == "completed" else None,
                'completed_at': datetime.now().isoformat() if status_str in ["completed", "failed"] else None
            }

            # 保存构造的结果到 Redis
            redis_conn.hset(RESULT_HASH, task_id, json.dumps(result))

        return result
    except Exception as e:
        logger.error(f"获取任务结果时发生错误: {str(e)}")
        return None

if __name__ == "__main__":
    # 启动工作进程
    logger.info("Using the configured Redis server")

    # 启动清理线程
    cleanup_thread = threading.Thread(target=cleanup_thread, daemon=True)
    cleanup_thread.start()

    # 启动工作进程数量
    worker_count = int(os.environ.get('WORKER_CONCURRENCY', '2'))
    workers = []

    for i in range(worker_count):
        worker = threading.Thread(target=worker_process, daemon=True)
        worker.start()
        workers.append(worker)
        logger.info(f"已启动工作进程 {i+1}/{worker_count}")

    # 等待所有工作进程完成（实际上不会完成，除非程序被终止）
    for worker in workers:
        worker.join()
