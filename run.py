import asyncio
import io
import logging
import re
from typing import AsyncGenerator

import gradio as gr
import matplotlib
from agents import Agent, Runner
from openai.types.responses import ResponseTextDeltaEvent
from PIL import Image

# 设置 Matplotlib 使用 Agg 后端，避免 GUI 警告
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化全局会话上下文
conversation_history = []


def extract_python_code(text):
    """
    从文本中提取 Python 代码块
    """
    # 查找 ```python 和 ``` 之间的代码
    pattern = r'```(?:python)?(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)

    if matches:
        return matches[0].strip()

    # 如果没有找到代码块，则尝试直接使用文本（假设整个文本是代码）
    return text.strip()


def process_code(code):
    """
    处理代码，注释掉 plt.show() 调用
    """
    # 替换 plt.show() 调用为注释
    code = re.sub(r'plt\.show\(\)', '# plt.show() - 已被注释', code)
    return code


def execute_plot_code(code):
    """
    执行绘图代码并返回图像
    """
    try:
        # 确保所有图形已关闭
        plt.close('all')

        # 创建一个局部命名空间来执行代码
        local_vars = {}
        local_vars.update(globals())

        # 确保 plt.figure() 被调用，以避免使用之前的图形
        if "plt.figure" not in code and "figure(" not in code:
            plt.figure()

        # 执行代码
        exec(code, globals(), local_vars)

        # 保存图像到内存
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)

        # 将图像转换为 PIL Image 对象
        img = Image.open(buf)
        plt.close('all')  # 关闭所有图形，避免内存泄漏

        return img
    except Exception as e:
        plt.close('all')  # 确保关闭任何打开的图形
        raise e


# 创建绘图专家代理
visualization_agent = Agent(
    name="数据可视化专家",
    instructions="""你是一个专业的数据可视化助手，专长于使用 Python 的 matplotlib 和 seaborn 库创建图表和可视化。

1. 分析用户的可视化需求，生成清晰易懂的 Python 代码。
2. 总是使用英文标点符号，不使用中文标点符号。
3. 代码必须符合 Python 语法，确保能够正确执行。
4. 不要在代码中包含 plt.show() 调用，因为图像会自动保存和显示。
5. 当可能时，包含示例数据以创建有意义的可视化。
6. 为图表添加合适的标题、标签和图例，美化视觉效果，调整字体大小和颜色，使视觉效果更好。
7. 代码应该包含必要的注释，解释关键步骤。
8. 确保使用适合数据类型的图表类型。
9. 回复时，首先简短解释你的实现方案，然后提供代码。
10. 如果用户要求改进图表，请参考之前的对话和代码，进行有针对性的改进。

始终以代码块格式回复，使用 ```python 和 ``` 标记代码。
""",
    model="gpt-4o",
)


async def generate_plot_with_agent(user_input, history=None):
    """
    使用 OpenAI Agents SDK 生成图表代码并执行
    """
    global conversation_history

    try:
        logger.info(f"开始处理用户输入: {user_input}")

        # 构建带有历史记录的提示
        if history and len(history) > 0:
            prompt = "请记住我们之前的对话：\n\n"
            for i, (user_msg, ai_msg) in enumerate(history):
                if user_msg and ai_msg:
                    prompt += f"用户: {user_msg}\n助手: {ai_msg}\n\n"
            prompt += f"现在，请根据以上对话历史和下面的新要求生成或改进数据可视化代码：{user_input}"
        else:
            prompt = f"请根据以下需求生成数据可视化代码：{user_input}"

        # 使用 Runner 直接运行 agent
        result = await Runner.run_streamed(visualization_agent, prompt)

        # 获取回复内容
        message_content = result.final_output
        print(message_content)

        # 将新对话添加到历史记录
        conversation_history.append({"role": "user", "content": user_input})
        conversation_history.append({"role": "assistant", "content": message_content})

        # 提取代码并处理
        code = extract_python_code(message_content)
        code = process_code(code)

        # 执行代码生成图表
        img = execute_plot_code(code)

        # 提取解释部分
        explanation = ""
        if "```" in message_content:
            explanation = message_content.split("```")[0].strip()

        logger.info("图表生成成功")
        return {
            "image": img,
            "code": code,
            "explanation": explanation,
            "full_response": message_content
        }
    except Exception as e:
        logger.error(f"生成图表时出错: {str(e)}")
        error_message = f"生成图表时出错: {str(e)}"
        if 'code' in locals():
            error_message += f"\n代码:\n{code}"
        return error_message


def chat_and_plot(user_message, chat_history, code_output):
    """
    处理用户输入并返回 AI 生成的回复和图表。
    """
    chat_history.append((user_message, "正在生成图表，请稍候..."))

    # 创建异步运行器，将当前的聊天历史传递给 agent
    result = asyncio.run(generate_plot_with_agent(user_message, chat_history[:-1]))

    if isinstance(result, dict):
        # 成功生成图表
        message = result[
            "full_response"] if "full_response" in result else "图表已生成！可以在右侧查看生成的图表和代码。您可以修改代码后点击'执行代码'按钮重新生成图表，或继续提问进行图表改进。"
        chat_history[-1] = (user_message, message)
        return chat_history, result["image"], result["code"]
    else:
        # 生成失败，result 包含错误信息
        message = result
        chat_history[-1] = (user_message, message)
        # 返回空图像和错误信息
        return chat_history, None, message


def execute_custom_code(code, chat_history):
    """
    执行用户修改后的代码并返回生成的图表
    """
    try:
        # 处理代码
        processed_code = process_code(code)
        # 执行代码生成图表
        img = execute_plot_code(processed_code)

        # 更新全局对话历史中最后一条助手消息的代码部分
        global conversation_history
        if conversation_history:
            last_assistant_msg = conversation_history[-1]
            if last_assistant_msg["role"] == "assistant":
                # 提取原始消息中的非代码部分（如果有）
                original_msg = last_assistant_msg["content"]
                explanation = ""
                if "```" in original_msg:
                    explanation = original_msg.split("```")[0].strip()

                # 构建新的消息内容，包含原始解释（如果有）和新代码
                new_content = f"{explanation}\n\n```python\n{processed_code}\n```" if explanation else f"```python\n{processed_code}\n```"
                last_assistant_msg["content"] = new_content

        # 添加执行结果到聊天历史
        chat_history.append({"role": "assistant", "content": "代码已执行，图表已更新。您可以继续提问进行进一步改进。"})
        return img, chat_history
    except Exception as e:
        error_message = f"执行代码时出错: {str(e)}"
        # 将错误消息添加到聊天历史
        chat_history.append({"role": "assistant", "content": error_message})
        return None, chat_history


def reset_conversation():
    """
    重置对话历史
    """
    global conversation_history
    conversation_history = []
    return [], None, ""


async def generate_plot_with_agent_stream(user_input) -> AsyncGenerator[dict, None]:
    """
    使用 OpenAI Agents SDK 生成图表代码并执行 - 流式版本
    """
    global conversation_history

    try:
        logger.info(f"开始处理用户输入: {user_input}")

        # 构建带有历史记录的提示
        if conversation_history:
            prompt = "请记住我们之前的对话：\n\n"
            for msg in conversation_history:
                if msg["role"] == "user":
                    prompt += f"用户: {msg['content']}\n"
                elif msg["role"] == "assistant":
                    prompt += f"助手: {msg['content']}\n\n"
            prompt += f"现在，请根据以上对话历史和下面的新要求生成或改进数据可视化代码：{user_input}"
        else:
            prompt = f"请根据以下需求生成数据可视化代码：{user_input}"

        # 使用 Runner.run_streamed 流式运行 agent
        result = Runner.run_streamed(visualization_agent, prompt)
        full_response = ""

        # 流式处理结果
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                delta_text = event.data.delta
                if delta_text:
                    full_response += delta_text
                    await asyncio.sleep(0.01)  # 添加小延迟使流更自然
                    yield {
                        "full_response": full_response,
                        "code": None,
                        "image": None,
                        "is_complete": False
                    }

        # 记录完整的会话历史
        conversation_history.append({"role": "user", "content": user_input})
        conversation_history.append({"role": "assistant", "content": full_response})

        # 检查是否包含 Python 代码块
        code = extract_python_code(full_response)
        if code and any(keyword in code.lower() for keyword in ['plt.', 'plot', 'figure', 'subplot', 'seaborn']):
            # 包含绘图相关代码，执行绘图操作
            code = process_code(code)
            img = execute_plot_code(code)
            logger.info("图表生成成功")

            # 返回最终的完整结果
            yield {
                "full_response": full_response,
                "code": code,
                "image": img,
                "is_complete": True
            }
        else:
            # 不包含绘图相关代码，直接返回对话内容
            yield {
                "full_response": full_response,
                "code": code if code else None,
                "image": None,
                "is_complete": True
            }

    except Exception as e:
        logger.error(f"处理请求时出错: {str(e)}")
        error_message = f"处理请求时出错: {str(e)}"
        if 'code' in locals():
            error_message += f"\n代码:\n{code}"
        yield {
            "full_response": error_message,
            "code": None,
            "image": None,
            "is_complete": True,
            "error": True
        }


async def chat_and_plot_stream(user_message, chat_history, code_output):
    """
    处理用户输入并返回 AI 生成的流式回复和图表。
    """
    try:
        # 添加用户消息到聊天历史
        chat_history = chat_history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": ""}]
        yield chat_history, None, code_output

        # 创建流式响应
        async for result in generate_plot_with_agent_stream(user_message):
            # 更新聊天历史中最后一条消息的回复部分
            current_response = result["full_response"]
            chat_history[-1]["content"] = current_response

            # 如果生成完成，检查是否有图像和代码
            if result["is_complete"]:
                if "error" in result and result["error"]:
                    # 处理错误情况
                    yield chat_history, None, result.get("code", "")
                else:
                    # 处理成功情况，可能有或没有图像
                    yield chat_history, result.get("image"), result.get("code", code_output)
            else:
                # 流式更新聊天内容，但不更新图像和代码
                yield chat_history, None, code_output

    except Exception as e:
        error_message = f"处理请求时出错: {str(e)}"
        chat_history[-1]["content"] = error_message
        yield chat_history, None, code_output


with gr.Blocks(title="Deeplot", theme="soft") as app:
    gr.Markdown("## 🎨 Deeplot")
    gr.Markdown("输入您的绘图需求，Deeplot 将生成对应的图表和代码。您可以持续对话来改进图表。")

    with gr.Row():
        with gr.Column(scale=1):
            # 更新 Chatbot 组件，使用 messages 类型
            chatbot = gr.Chatbot(
                label="与 Deeplot 交流",
                height=500,
                type="messages"  # 使用新的消息格式
            )
            user_input = gr.Textbox(
                label="请输入您的绘图需求或改进建议",
                placeholder="例如：绘制一个展示不同月份销售额的柱状图，添加适当的标题和标签"
            )
            with gr.Row():
                send_btn = gr.Button("发送", variant="primary")
                clear_btn = gr.Button("清空对话")

        with gr.Column(scale=1):
            with gr.Tab("图表"):
                plot_output = gr.Image(label="生成的图表", type="pil")
            with gr.Tab("代码"):
                code_output = gr.Code(language="python", label="生成的代码", interactive=True)
                execute_btn = gr.Button("执行代码", variant="secondary")

    # 添加使用说明
    with gr.Accordion("使用说明", open=False):
        gr.Markdown("""
        ### 🔍 如何使用
        1. 在输入框中描述您想要创建的图表
        2. 点击"发送"按钮
        3. 在右侧查看生成的图表和对应的 Python 代码
        4. 您可以：
           - 修改代码后点击"执行代码"按钮重新生成图表
           - 继续对话，要求Deeplot改进或修改图表
           - 点击"清空对话"按钮开始新的对话

        ### 💡 示例提示
        - "绘制一个展示2010-2023年中国GDP增长的折线图"
        - "使用气泡图展示人口、寿命和GDP三个变量之间的关系"
        - "创建一个热力图展示不同时间段的数据分布情况"
        - "生成一个饼图展示不同类别的市场份额，并添加百分比标签"
        - "使用小提琴图比较不同组别的数据分布"
        - "能否将图表颜色改为蓝色系？"
        - "请给图表添加网格线，使数据更易读"
        - "可以将图例移到右上角吗？"
        """)

    # 发送按钮绑定流式函数
    send_btn.click(
        fn=chat_and_plot_stream,
        inputs=[user_input, chatbot, code_output],
        outputs=[chatbot, plot_output, code_output],
        api_name="chat_stream"  # 添加 API 名称以支持流式输出
    ).then(
        fn=lambda: "",
        inputs=[],
        outputs=[user_input]  # 清空输入框
    )

    # 保留清空对话和执行代码按钮的原逻辑
    clear_btn.click(fn=reset_conversation, inputs=[], outputs=[chatbot, plot_output, code_output])

    execute_btn.click(
        fn=execute_custom_code,
        inputs=[code_output, chatbot],
        outputs=[plot_output, chatbot]
    )

if __name__ == "__main__":
    # 先配置队列，再启动应用
    app.queue()
    app.launch(server_name="0.0.0.0", server_port=7860)
