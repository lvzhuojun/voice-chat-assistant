# Voice Chat Assistant

基于 GPT-SoVITS 的语音对话 Web 应用，配合 [voice-cloning-service](../voice-cloning-service) 使用克隆好的音色进行实时语音对话。

## 项目简介

本项目是整个语音克隆对话系统的第二部分：

```
voice-cloning-service  ──音色训练──▶  storage/models/{voice_id}/
                                               │
voice-chat-assistant   ◀──导入──────────────┘
       │
       ├── STT (faster-whisper)：用户语音 → 文字
       ├── LLM (OpenAI 兼容)：文字 → AI 回复
       └── TTS (GPT-SoVITS)：AI 回复 → 克隆音色语音
```

## 与项目一（voice-cloning-service）的关系

项目一训练完成后，每个音色产出以下文件：

```
storage/models/{voice_id}/
├── {voice_id}_gpt.ckpt        # GPT 模型权重
├── {voice_id}_sovits.pth      # SoVITS 模型权重
├── metadata.json              # 元数据（名称、语言、训练参数等）
└── reference.wav              # 参考音频（推理必须）
```

详细导入步骤见 [docs/VOICE_MODEL_IMPORT.md](docs/VOICE_MODEL_IMPORT.md)。

## 快速开始

### 前置要求

- Windows 11 / Linux（生产）
- CUDA 12.8+（RTX 5060 / Blackwell 已测试）
- Conda（Miniconda 或 Anaconda）
- Git（配置好 SSH Key）

### 6 步运行

```bash
# 1. 克隆本项目
git clone git@github.com:lvzhuojun/voice-chat-assistant.git
cd voice-chat-assistant

# 2. 创建 conda 环境 & 安装依赖
setup\install.bat          # Windows
# 或手动：conda env create -f environment.yml

# 3. 克隆 GPT-SoVITS 源码
setup\clone_gptsovits.bat

# 4. 下载预训练模型（中文 HuBERT + RoBERTa）
conda activate voice-chat
python setup/download_models.py

# 5. 复制环境变量 & 配置
cp .env.example .env
# 编辑 .env：填写 DATABASE_URL、JWT_SECRET_KEY、LLM_API_KEY（可选）

# 6. 启动所有服务
start.bat
```

浏览器访问 http://localhost:5173

### 停止服务

```bash
stop.bat
```

## 架构概述

详见 [ARCHITECTURE.md](ARCHITECTURE.md)。

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + Vite + TailwindCSS + shadcn/ui |
| 后端 | FastAPI + SQLAlchemy + Alembic |
| 数据库 | PostgreSQL + Redis |
| STT | faster-whisper（medium，CUDA） |
| LLM | OpenAI 兼容接口（Key 为空时 mock） |
| TTS | GPT-SoVITS v2（对接项目一模型） |
| 通信 | WebSocket 全双工 |

## 目录结构

```
voice-chat-assistant/
├── frontend/          # React 前端
├── backend/           # FastAPI 后端
├── setup/             # 安装脚本
├── docker/            # Docker 配置
├── docs/              # 文档
└── storage/           # 运行时数据（gitignore）
    ├── voice_models/  # 导入的音色模型
    └── pretrained_models/GPT-SoVITS/  # 预训练模型
```

## 环境要求

- Python 3.10（conda 环境 voice-chat）
- Node.js ≥ 20（通过 conda 安装）
- PostgreSQL 14+
- Redis 7+
- FFmpeg（音频转换，conda 环境中自动安装）

## 文档

- [API 文档](docs/API.md)
- [部署指南](docs/DEPLOY.md)
- [音色模型导入](docs/VOICE_MODEL_IMPORT.md)
- [系统架构](ARCHITECTURE.md)
