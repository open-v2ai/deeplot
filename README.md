# Deeplot: 聊天即绘图

**Deeplot** 是一个基于 Gradio 和 Agents 的打造的对话生成图表工具！

[🔗在线试用](https://research.arxivs.com/deeplot)

## 1 功能特点

- [x] 🖥️ 简洁直观的 Web 界面
- [x] 📊 支持 Matplotlib、Seaborn 等主流绘图库
- [x] 📥 支持图像下载功能

- [ ] 🀄 完善的中文字体支持，自动适配不同操作系统
- [ ] 🔒 通过 Graudrail，增加代码安全

## 2 安装说明

>⚠️ 请使用 Python 3.11 及更新版本。

### 2.1 本地部署

1. 克隆仓库到本地：

    ```bash
    git clone https://github.com/open-v2ai/deeplot.git
    cd deeplot
    ```

2. 安装依赖：

    ```bash
    pip install -r requirements.txt
    ```

3. 运行应用：

    ```bash
    # 设置 OpenAI API Key
    export OPENAI_API_KEY="sk-******"
    # 如果需要使用代理，请设置 OPENAI_BASE_URL
    export OPENAI_BASE_URL="https://api.openai.com/v1"

    # 运行应用
    python run.py
    ```

### 2.2 Docker 部署

1. 克隆仓库到本地：

    ```bash
    git clone https://github.com/open-v2ai/deeplot.git

    cd deeplot
    ```

2. 打包镜像

    ```bash
    docker build -t deeplot:1.0.0 -f ./Dockerfile .
    ```

3. 运行容器

    ```bash
    docker run -d --name deeplot --restart=always \
      -e OPENAI_API_KEY="sk-******" \
      -e OPENAI_BASE_URL="https://api.openai.com/v1" \
      -p 7860:7860 deeplot:1.0.0
    ```

## 3 使用说明

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

## 4 许可证

本项目采用 MIT 开源许可证。
