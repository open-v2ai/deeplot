# 设置 matplotlib 为非交互模式，避免在线程中创建 GUI 窗口
import matplotlib
matplotlib.use('Agg')  # 使用 Agg 后端，不需要 GUI

import matplotlib.pyplot as plt
import io
from PIL import Image
import matplotlib as mpl
import platform
import os
import sys
import traceback

# 配置中文字体支持
def configure_chinese_font():
    # 保存原始字体配置
    original_font = mpl.rcParams['font.sans-serif'].copy()

    # 根据系统添加合适的中文字体
    system = platform.system()
    if system == 'Windows':
        chinese_fonts = ['Microsoft YaHei', 'SimHei', 'Arial']
    elif system == 'Darwin':  # macOS
        chinese_fonts = ['Arial Unicode MS', 'PingFang SC', 'Heiti SC', 'STHeiti', 'Arial']
    else:  # Linux
        # 在Linux上尝试更多通用字体
        chinese_fonts = ['DejaVu Sans', 'Liberation Sans', 'WenQuanYi Micro Hei', 'Droid Sans Fallback', 'Noto Sans CJK SC', 'Noto Sans CJK TC', 'Arial']

    # 将中文字体添加到字体列表的前面，而不是完全替换
    mpl.rcParams['font.sans-serif'] = chinese_fonts + original_font
    mpl.rcParams['axes.unicode_minus'] = False  # 正确显示负号

# 应用中文字体配置
configure_chinese_font()

def execute_python_code(code, output_path=None):
    """
    执行 Python 代码并生成图像

    Args:
        code: 要执行的 Python 代码
        output_path: 图像保存路径，如果为 None 则不保存

    Returns:
        (result, error): 结果和错误信息的元组
    """
    print(f"开始执行代码，输出路径: {output_path}")

    # 创建一个内存中的图像缓冲区
    buf = io.BytesIO()

    try:
        # 清除之前的图形
        plt.clf()
        plt.close('all')

        # 使用更简单的方法处理中文字体
        font_setup_code = """
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# 尝试找到可用的中文字体
def find_chinese_font():
    fonts_to_try = [
        'Noto Sans CJK SC', 'Noto Sans CJK TC', 'Noto Sans CJK JP',
        'WenQuanYi Micro Hei', 'Droid Sans Fallback', 'SimHei',
        'Microsoft YaHei', 'PingFang SC', 'STHeiti', 'Arial Unicode MS'
    ]

    for font in fonts_to_try:
        if any(font.lower() in f.name.lower() for f in fm.fontManager.ttflist):
            return font
    return None

# 找到中文字体
chinese_font = find_chinese_font()

# 设置全局字体
if chinese_font:
    plt.rcParams['font.sans-serif'] = [chinese_font] + plt.rcParams['font.sans-serif']
    plt.rcParams['axes.unicode_minus'] = False
"""
        # 先执行字体设置代码
        try:
            exec(font_setup_code, globals())
        except Exception as font_error:
            print(f"设置字体时出错: {str(font_error)}")
            # 继续执行，不要因为字体问题中断

        # 执行用户代码
        print("执行用户代码...")

        # 创建一个安全的执行环境
        safe_globals = {
            'plt': plt,
            'np': __import__('numpy'),
            'pd': __import__('pandas'),
            'sns': __import__('seaborn'),
            'Image': Image,
            'io': io,
            'os': os,
            'sys': sys,
            'traceback': __import__('traceback'),
            'math': __import__('math'),
            'random': __import__('random'),
            'time': __import__('time'),
            'datetime': __import__('datetime'),
        }

        # 执行代码
        exec(code, safe_globals)

        # 检查是否有图形对象
        if plt.get_fignums():
            print(f"检测到图形对象，数量: {len(plt.get_fignums())}")

            try:
                # 保存图形到缓冲区
                plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
                buf.seek(0)

                # 转换为PIL图像并复制到内存中，这样可以安全关闭原始缓冲区
                img = Image.open(buf).copy()

                # 如果提供了输出路径，保存图像
                if output_path:
                    print(f"保存图像到: {output_path}")
                    # 确保目录存在
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    img.save(output_path)
                    print(f"图像已保存: {os.path.exists(output_path)}")

                return True, None
            except Exception as save_error:
                print(f"保存图像时出错: {str(save_error)}")
                return False, f"保存图像时出错: {str(save_error)}"
        else:
            print("没有检测到图形对象")
            # 创建一个带有文本的图像，提示用户没有生成图像
            try:
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.text(0.5, 0.5, "代码执行成功，但没有生成图像。\n请确保代码中包含绘图命令。",
                       ha='center', va='center', fontsize=14)
                ax.axis('off')
                plt.savefig(buf, format='png')
                buf.seek(0)
                img = Image.open(buf).copy()

                # 如果提供了输出路径，保存图像
                if output_path:
                    print(f"保存提示图像到: {output_path}")
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    img.save(output_path)
                    print(f"提示图像已保存: {os.path.exists(output_path)}")

                return True, "代码执行成功，但没有生成图像。请确保代码中包含绘图命令。"
            except Exception as img_error:
                print(f"创建提示图像时出错: {str(img_error)}")
                return False, f"创建提示图像时出错: {str(img_error)}"

    except Exception as e:
        print(f"代码执行错误: {str(e)}")
        import traceback
        traceback_str = traceback.format_exc()
        print(traceback_str)

        # 获取详细的错误信息
        error_msg = f"代码执行错误: {str(e)}\n{traceback_str}"

        try:
            # 创建一个带有错误信息的图像
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, error_msg, ha='center', va='center', fontsize=12, color='red')
            ax.axis('off')
            plt.savefig(buf, format='png')
            buf.seek(0)
            img = Image.open(buf).copy()

            # 如果提供了输出路径，保存错误图像
            if output_path:
                print(f"保存错误图像到: {output_path}")
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                img.save(output_path)
                print(f"错误图像已保存: {os.path.exists(output_path)}")

            return False, error_msg
        except Exception as img_error:
            print(f"创建错误图像时出错: {str(img_error)}")
            return False, f"{error_msg}\n创建错误图像时出错: {str(img_error)}"

    finally:
        try:
            # 关闭缓冲区
            buf.close()
            # 关闭所有图形
            plt.close('all')
        except:
            pass
        print("代码执行完成")

# 如果直接运行此脚本，可以作为独立的 worker
if __name__ == "__main__":
    # 这里可以实现从消息队列接收任务的逻辑
    pass
