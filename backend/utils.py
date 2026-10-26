import os
import shutil
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def clean_old_files(directory, max_age_hours=24):
    """
    清理指定目录中超过一定时间的文件

    Args:
        directory: 要清理的目录
        max_age_hours: 文件最大保留时间（小时）
    """
    if not os.path.exists(directory):
        logger.warning(f"目录不存在，无法清理: {directory}")
        return

    now = datetime.now()
    count_removed = 0

    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)

        # 跳过目录
        if os.path.isdir(file_path):
            continue

        # 获取文件修改时间
        file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))

        # 如果文件超过最大保留时间，删除它
        if now - file_mod_time > timedelta(hours=max_age_hours):
            try:
                os.remove(file_path)
                count_removed += 1
            except Exception as e:
                logger.error(f"删除文件 {file_path} 时发生错误: {e}")

    if count_removed > 0:
        logger.info(f"已从 {directory} 清理 {count_removed} 个旧文件")

def ensure_directory(directory):
    """确保目录存在"""
    try:
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"确保目录存在: {directory}")
    except Exception as e:
        logger.error(f"创建目录 {directory} 时发生错误: {e}")
        raise
