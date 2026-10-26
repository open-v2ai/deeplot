document.addEventListener('DOMContentLoaded', function() {
    // 配置 API 端点 - 使用相对路径
    const API_URL = '/api';  // 使用相对路径，由前端服务器代理

    // 初始化代码编辑器
    const codeInput = document.getElementById('code-input');
    const editor = CodeMirror.fromTextArea(codeInput, {
        mode: 'python',
        theme: 'monokai',
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        autoCloseBrackets: true,
        matchBrackets: true
    });

    // 设置默认代码
    const defaultCode = `import matplotlib.pyplot as plt
import numpy as np
import matplotlib.font_manager as fm

# 生成数据
x = np.linspace(0, 10, 100)
y = np.sin(x)

# 创建图表
plt.figure(figsize=(10, 6))
plt.plot(x, y, 'b-', linewidth=2)

# 设置标题和标签
plt.title('正弦波')
plt.xlabel('x')
plt.ylabel('sin(x)')
plt.grid(True)`;

    editor.setValue(defaultCode);

    // 示例代码
    const examples = [
        // 示例1: 正弦波
    `import matplotlib.pyplot as plt
    import numpy as np

    x = np.linspace(0, 10, 100)
    y = np.sin(x)

    plt.figure(figsize=(10, 6))
    plt.plot(x, y, 'b-', linewidth=2)
    plt.title('正弦波')
    plt.xlabel('x')
    plt.ylabel('sin(x)')
    plt.grid(True)`,

        // 示例2: 柱状图
    `import matplotlib.pyplot as plt
    import numpy as np

    # 创建数据
    categories = ['A', 'B', 'C', 'D', 'E']
    values = [22, 35, 14, 28, 19]

    # 创建柱状图
    plt.figure(figsize=(10, 6))
    plt.bar(categories, values, color='skyblue')
    plt.title('简单柱状图')
    plt.xlabel('类别')
    plt.ylabel('数值')
    plt.grid(True, axis='y', linestyle='--', alpha=0.7)`,

        // 示例3: 饼图
        `import matplotlib.pyplot as plt
import numpy as np

# 创建数据
labels = ['苹果', '香蕉', '橙子', '葡萄', '西瓜']
sizes = [25, 20, 15, 30, 10]
colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#c2c2f0']
explode = (0.1, 0, 0, 0, 0)  # 突出第一个切片

# 创建饼图
plt.figure(figsize=(10, 8))
plt.pie(sizes, explode=explode, labels=labels, colors=colors,
        autopct='%1.1f%%', shadow=True, startangle=90)
plt.axis('equal')  # 确保饼图是圆的
plt.title('水果比例')`
    ];

    // 加载示例代码
    const exampleButtons = document.querySelectorAll('.example-button');
    exampleButtons.forEach(button => {
        button.addEventListener('click', function() {
            const exampleIndex = parseInt(this.getAttribute('data-example'));
            if (exampleIndex >= 0 && exampleIndex < examples.length) {
                editor.setValue(examples[exampleIndex]);
            }
        });
    });

    // 执行代码按钮
    const runButton = document.getElementById('run-button');
    const resultImage = document.getElementById('result-image');
    const loading = document.getElementById('loading');
    const errorMessage = document.getElementById('error-message');

    runButton.addEventListener('click', async function() {
        // 显示加载状态
        loading.classList.remove('hidden');
        errorMessage.classList.add('hidden');
        resultImage.src = '';
        runButton.disabled = true;
        runButton.textContent = '处理中...';

        try {
            // 获取代码
            const code = editor.getValue();

            // 发送到后端
            const response = await fetch(`${API_URL}/execute`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ code: code })
            });

            if (!response.ok) {
                throw new Error(`服务器响应错误: ${response.status}`);
            }

            const data = await response.json();
            const taskId = data.task_id;

            // 轮询任务状态
            await pollTaskStatus(taskId);

        } catch (error) {
            loading.classList.add('hidden');
            errorMessage.textContent = '发生错误: ' + error.message;
            errorMessage.classList.remove('hidden');
        } finally {
            runButton.disabled = false;
            runButton.textContent = '执行代码';
        }
    });

    // 轮询任务状态
    async function pollTaskStatus(taskId) {
        const maxAttempts = 60;  // 最多轮询60次（约60秒）
        let attempts = 0;

        const poll = async () => {
            if (attempts >= maxAttempts) {
                throw new Error('任务执行超时');
            }

            attempts++;

            try {
                const response = await fetch(`${API_URL}/status/${taskId}`);

                if (!response.ok) {
                    throw new Error(`获取任务状态失败: ${response.status}`);
                }

                const data = await response.json();

                if (data.status === 'completed') {
                    // 任务完成，显示结果
                    loading.classList.add('hidden');

                    if (data.image_url) {
                        resultImage.src = data.image_url + '?t=' + new Date().getTime();
                    }

                    return;
                } else if (data.status === 'failed') {
                    // 任务失败，显示错误
                    loading.classList.add('hidden');
                    errorMessage.textContent = data.error || '任务执行失败';
                    errorMessage.classList.remove('hidden');
                    return;
                } else {
                    // 任务仍在处理中，继续轮询
                    setTimeout(poll, 1000);  // 每秒轮询一次
                }
            } catch (error) {
                loading.classList.add('hidden');
                errorMessage.textContent = '轮询任务状态失败: ' + error.message;
                errorMessage.classList.remove('hidden');
            }
        };

        await poll();
    }
});
