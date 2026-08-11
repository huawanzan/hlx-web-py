# 葫芦侠自动化工具 - Python Web版

> 一个基于 Flask 的葫芦侠社区自动化工具，支持自动发帖、评论、签到等功能

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Flask Version](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

## ✨ 功能特性

### 核心功能

- 🔐 **账号登录** - 支持葫芦侠账号密码登录
- ✅ **全板块签到** - 一键完成所有板块的自动签到
- 📝 **自动发帖** - 支持三种发帖模式
  - 普通模式：纯文字或文字+图片
  - 图文混编：图文交错排版
  - 情头模式：特殊情侣头像发帖
- 💬 **自动评论** - 批量自动评论指定帖子
- 🖼️ **智能图片压缩** - 自动压缩超过12MB的图片
- 📊 **实时日志** - Web界面实时显示操作日志
- 🎨 **美观界面** - 响应式设计，支持多设备访问

### 技术特点

- Flask 后端 + 原生 JavaScript 前端
- SSE (Server-Sent Events) 实时通信
- 智能图片压缩算法
- 完整的API签名验证
- 线程安全的任务管理

## 📸 界面预览

界面采用紧凑的网格布局，黑底绿字的日志区域，操作简单直观。

![登录界面](images/README/screenshot1.png)

![发帖功能](images/README/screenshot2.png)

![评论功能](images/README/screenshot3.png)

## 🚀 快速开始

### 环境要求

- Python 3.7 或更高版本
- pip 包管理器

### 安装步骤

1. **克隆项目**

```bash
git clone https://github.com/YOUR_USERNAME/hlx-web-py.git
cd hlx-web-py
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **准备图片**（可选）

```bash
# 将要发布的图片放入 images 目录
# 项目已包含6张示例图片可直接使用
```

4. **启动应用**

```bash
python app.py
```

5. **访问界面**

```
打开浏览器访问：http://localhost:5000
```

## 📖 使用说明

### 登录账号

1. 在顶部输入葫芦侠账号和密码
2. 点击"登录"按钮
3. 登录成功后会显示用户昵称

### 全板块签到

1. 登录成功后，"签到"按钮会激活
2. 点击"签到"即可完成所有板块的自动签到

### 自动发帖

1. 切换到"发帖"标签
2. 配置发帖参数：
   - **板块ID**：目标板块编号（默认57）
   - **标签ID**：帖子标签（0为无标签）
   - **发帖数量**：要发布的帖子数量
   - **发帖模式**：普通/图文混编/情头
   - **每帖图片数**：每个帖子包含的图片数量（0-9）
   - **图片目录**：图片所在文件夹路径
   - **上传延迟**：图片上传间隔（毫秒）
   - **发帖延迟**：发帖间隔（毫秒）
3. 输入签名内容（用英文逗号分隔，格式：标题1,内容1,标题2,内容2...）
4. 点击"开始发帖"

**签名格式示例：**

```
标题一，可以有中文逗号,内容一，也可以有中文逗号,标题二,内容二
```

### 自动评论

1. 切换到"评论"标签
2. 配置评论参数：
   - **帖子ID**：要评论的帖子编号
   - **每评论图片数**：每条评论的图片数量
   - **图片目录**：图片所在文件夹
   - **评论延迟**：评论间隔（毫秒）
   - **情头模式**：是否启用（需要couplemid.jpg文件）
3. 输入评论文本（每行一条）
4. 点击"开始评论"

## 📁 项目结构

```
hlx-web-py/
├── app.py                  # Flask 后端主程序（1420行）
├── templates/
│   └── index.html         # Web 前端界面（943行）
├── static/
│   └── back/
│       └── 1778562504132.png  # 背景图片
├── images/                # 图片目录（示例图片）
├── requirements.txt       # Python 依赖
├── README.md             # 项目说明
├── .gitignore            # Git 忽略配置
└── start.bat             # Windows 快速启动脚本
```

## 🔧 配置说明

### 图片目录

- 默认使用 `images` 目录（相对路径）
- 可以指定绝对路径，如 `D:\pictures`
- 支持 JPG、PNG、WEBP 等常见格式
- 图片超过12MB会自动压缩

### 图片压缩策略

1. **质量压缩**：逐步降低质量（95→90→85...→5）
2. **尺寸压缩**：如果质量压缩不够，按比例缩小尺寸
3. **格式转换**：PNG自动转为JPEG以减小体积

### 情头模式

- 需要在根目录放置 `couplemid.jpg` 作为中间图
- 自动在两张图片之间插入中间图

## ⚙️ 环境变量（可选）

可以通过环境变量自定义配置：

```bash
export FLASK_PORT=5000        # 服务端口
export FLASK_DEBUG=True       # 调试模式
```

## 🛡️ 安全建议

- 不要在公网暴露此应用
- 建议在局域网内使用
- 不要分享你的账号密码
- 定期更换密码

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📝 更新日志

### v1.0.0 (2026-08-11)

- ✨ 初始版本发布
- ✅ 支持自动发帖和评论
- ✅ 智能图片压缩
- ✅ Web界面操作
- ✅ 实时日志显示

## ❓ 常见问题

**Q: 登录失败怎么办？**
A: 检查账号密码是否正确，确保网络连接正常。

**Q: 图片上传失败？**
A: 确保图片目录路径正确，图片格式支持，且图片文件没有损坏。

**Q: 发帖被限制？**
A: 适当增加发帖延迟时间，避免操作过于频繁。

**Q: 如何获取板块ID？**
A: 访问葫芦侠对应板块，从URL中查看板块编号。

## 📄 免责声明

本项目仅供学习交流使用，请勿用于商业用途或违反相关法律法规的行为。使用本工具产生的任何后果由使用者自行承担。

## 📧 联系方式

- 提交 Issue：[GitHub Issues](https://github.com/YOUR_USERNAME/hlx-web-py/issues)
- 邮箱：your-email@example.com

## 📜 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

---

⭐ 如果这个项目对你有帮助，欢迎 Star 支持！
