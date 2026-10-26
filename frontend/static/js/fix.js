// 在页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 获取DOM元素
    const codeInput = document.getElementById('code-input');
    const submitBtn = document.getElementById('submit-btn');
    const loadingIndicator = document.getElementById('loading-indicator');
    const resultContainer = document.getElementById('result-container');
    const resultImage = document.getElementById('result-image');
    const imageSource = document.getElementById('image-source');
    const imageError = document.getElementById('image-error');
    const loading = document.getElementById('loading');
    const errorMessage = document.getElementById('error-message');

    // 初始化代码编辑器
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

# 生成数据
x = np.linspace(0, 10, 100)
y = np.sin(x)

# 创建图表
plt.figure(figsize=(8, 8))
plt.plot(x, y, 'b-', linewidth=2)

# 设置标题和标签
plt.title('正弦波')
plt.xlabel('x')
plt.ylabel('sin(x)')
plt.grid(True)
plt.tight_layout()`;

    editor.setValue(defaultCode);

    // 示例代码
    const examples = [
        // 示例1: 正弦波
        `import matplotlib.pyplot as plt
import numpy as np

# 生成数据
x = np.linspace(0, 10, 100)
y = np.sin(x)

# 创建正方形图表
plt.figure(figsize=(8, 8))
plt.plot(x, y, 'b-', linewidth=2)
plt.title('正弦波')
plt.xlabel('x')
plt.ylabel('sin(x)')
plt.grid(True)
plt.tight_layout()`,

        // 示例2: 柱状图
        `import matplotlib.pyplot as plt
import numpy as np

# 创建数据
categories = ['A', 'B', 'C', 'D', 'E']
values = [22, 35, 14, 28, 19]

# 创建正方形柱状图
plt.figure(figsize=(8, 8))
plt.bar(categories, values, color='skyblue')
plt.title('简单柱状图')
plt.xlabel('类别')
plt.ylabel('数值')
plt.grid(True, axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()`,

        // 示例3: 饼图
        `import matplotlib.pyplot as plt
import numpy as np

# 创建数据
labels = ['苹果', '香蕉', '橙子', '葡萄', '西瓜']
sizes = [25, 20, 15, 30, 10]
colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#c2c2f0']
explode = (0.1, 0, 0, 0, 0)  # 突出第一个切片

# 创建正方形饼图
plt.figure(figsize=(8, 8))
plt.pie(sizes, explode=explode, labels=labels, colors=colors,
        autopct='%1.1f%%', shadow=True, startangle=90)
plt.axis('equal')  # 确保饼图是圆的
plt.title('水果比例')
plt.tight_layout()`
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
    submitBtn.addEventListener('click', async function() {
        console.log("点击执行代码按钮");
        // 显示加载状态
        if (loading) loading.classList.remove('hidden');
        if (errorMessage) errorMessage.classList.add('hidden');
        if (resultImage) resultImage.src = '';

        // 重置图像错误显示
        if (imageError) imageError.style.display = 'none';

        submitBtn.disabled = true;

        try {
            // 获取代码
            const code = editor.getValue();
            console.log("提交代码:", code);

            if (!code.trim()) {
                throw new Error("请输入Python代码后再执行");
            }

            // 发送到后端
            const response = await fetch('/api/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ code: code })
            });

            if (!response.ok) {
                throw new Error(`服务器响应错误: ${response.status} - ${response.statusText}`);
            }

            const data = await response.json();
            const taskId = data.task_id;
            console.log("获取任务ID:", taskId);

            // 轮询任务状态
            await pollTaskStatus(taskId);

        } catch (error) {
            console.error("执行代码出错:", error);
            if (loading) loading.classList.add('hidden');
            if (errorMessage) {
                errorMessage.textContent = '执行错误: ' + error.message;
                errorMessage.classList.remove('hidden');
                // 确保错误信息区域可见
                errorMessage.style.display = 'block';
            }
        } finally {
            submitBtn.disabled = false;
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
            console.log(`轮询任务状态 (${attempts}/${maxAttempts}): ${taskId}`);

            try {
                const response = await fetch(`/api/status/${taskId}`);

                if (!response.ok) {
                    throw new Error(`获取任务状态失败: ${response.status}`);
                }

                const data = await response.json();
                console.log("任务状态:", data);

                if (data.status === 'completed') {
                    // 任务完成，显示结果
                    if (loading) loading.classList.add('hidden');
                    if (resultContainer) resultContainer.style.display = 'block';

                    if (data.image_url && resultImage) {
                        // 使用URL图像
                        // 修复图像URL路径
                        let imageUrl = data.image_url;
                        console.log("图像URL:", imageUrl);
                        // 添加时间戳防止缓存
                        resultImage.src = imageUrl + '?t=' + new Date().getTime();
                        resultImage.style.display = 'block';
                        if (imageError) imageError.style.display = 'none';

                        // 确保图像容器可见
                        if (document.getElementById('result-container')) {
                            document.getElementById('result-container').style.display = 'block';
                        }
                        if (document.getElementById('image-wrapper')) {
                            document.getElementById('image-wrapper').style.display = 'block';
                        }

                        // 添加错误处理
                        resultImage.onerror = function() {
                            console.error('图像加载失败:', imageUrl);

                            // 尝试使用备用URL
                            if (imageUrl.startsWith('/static/images/')) {
                                const backupUrl = '/api/images/' + imageUrl.split('/').pop();
                                console.log('尝试备用URL:', backupUrl);
                                resultImage.src = backupUrl + '?t=' + new Date().getTime();
                                if (imageSource) imageSource.textContent = `尝试备用URL: ${backupUrl}`;

                                // 如果备用URL也失败
                                resultImage.onerror = function() {
                                    console.error('备用URL也加载失败:', backupUrl);
                                    resultImage.style.display = 'none';
                                    if (imageError) imageError.style.display = 'block';
                                };
                            } else {
                                resultImage.style.display = 'none';
                                if (imageError) imageError.style.display = 'block';
                            }
                        };
                    } else {
                        // 没有图像
                        if (resultImage) resultImage.style.display = 'none';
                        if (imageError) imageError.style.display = 'block';
                    }

                    return;
                } else if (data.status === 'failed') {
                    // 任务失败，显示错误
                    if (loading) loading.classList.add('hidden');
                    if (errorMessage) {
                        // 确保错误信息显示
                        errorMessage.textContent = data.error || '代码执行失败，请检查您的代码是否有语法错误或运行时错误';
                        errorMessage.classList.remove('hidden');
                        console.error("代码执行失败:", data.error);
                    }
                    return;
                } else {
                    // 任务仍在处理中，继续轮询
                    setTimeout(poll, 1000);  // 每秒轮询一次
                }
            } catch (error) {
                console.error("轮询任务状态出错:", error);
                if (loading) loading.classList.add('hidden');
                if (errorMessage) {
                    errorMessage.textContent = '轮询任务状态失败: ' + error.message;
                    errorMessage.classList.remove('hidden');
                    errorMessage.style.display = 'block';
                }
            }
        };

        await poll();
    }
});
