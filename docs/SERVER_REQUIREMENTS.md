# 服务器部署需求说明

> 本文档用于选购/租用服务器时的参考，涵盖硬件要求、软件环境、模型体积、显存占用和推荐平台。

---

## 一、项目概述

这是一个**全栈实时语音对话助手**，技术栈如下：

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + Vite（构建后由 Nginx 托管静态文件） |
| 后端 | Python 3.10 + FastAPI + WebSocket |
| 数据库 | PostgreSQL 15 + Redis 7（Docker 部署） |
| STT | faster-whisper（medium 模型，GPU 推理） |
| LLM | OpenAI 兼容接口（调用外部 API，不在本机运行） |
| TTS | GPT-SoVITS v2（GPU 推理）/ CosyVoice 2（可选，GPU 推理） |
| 部署 | Docker Compose + conda 虚拟环境 + Nginx 反代 |

**数据流**：用户录音 → WebSocket → STT 识别文字 → LLM 流式生成回复 → 分句 TTS 合成音频 → 前端顺序播放

---

## 二、硬件最低要求

### GPU（核心瓶颈）

| 场景 | 最低 | 推荐 |
|------|------|------|
| 只用 GPT-SoVITS | 8 GB VRAM | 12 GB VRAM |
| GPT-SoVITS + CosyVoice 2 | 10 GB VRAM | 16 GB VRAM |

**显存占用明细（运行时）：**

| 组件 | 显存占用 |
|------|---------|
| faster-whisper medium | ~1.5 GB |
| GPT-SoVITS v2（LRU 缓存 1 个音色） | ~2–3 GB |
| CosyVoice 2（可选，加载后常驻） | ~1.5 GB |
| **仅 GPT-SoVITS 合计** | **~4–5 GB** |
| **含 CosyVoice 合计** | **~5–6 GB** |

> 结论：**8 GB VRAM 够用（仅 GPT-SoVITS），不开 CosyVoice 更安全**。
> 推荐 RTX 3080（10 GB）、RTX 3090（24 GB）、A10（24 GB）。

### CPU / RAM / 磁盘

| 项目 | 最低 | 推荐 |
|------|------|------|
| CPU | 4 核 | 8 核 |
| RAM（内存） | 16 GB | 32 GB |
| 磁盘 | 40 GB | 80 GB |
| 系统 | Ubuntu 20.04 | Ubuntu 22.04 LTS |

---

## 三、磁盘空间明细

| 内容 | 大小 |
|------|------|
| 系统 + Docker 镜像 + 依赖 | ~15 GB |
| GPT-SoVITS 源码 | ~500 MB |
| GPT-SoVITS 预训练模型（chinese-hubert-base 等） | ~1 GB |
| faster-whisper medium 模型 | ~1.5 GB |
| CosyVoice 2 模型（可选） | ~1.5 GB |
| 用户音色模型（每个 ~100–300 MB） | 视数量而定 |
| PostgreSQL 数据、日志 | ~1 GB |
| **合计（不含 CosyVoice）** | **~20 GB** |
| **合计（含 CosyVoice）** | **~22 GB** |

> 预留 40 GB 磁盘即可舒适运行；留 80 GB 则有充足余量。

---

## 四、软件环境要求

服务器上需要提前安装/具备：

```
Ubuntu 22.04 LTS
NVIDIA 驱动 545+（支持 CUDA 12.8）
CUDA Toolkit 12.8
Docker 24+
Docker Compose v2（docker compose 命令）
Git
Miniconda 或 Anaconda（用于 conda activate voice-chat）
```

> 如果选用的镜像已预装 CUDA + Docker + conda（如 AutoDL 镜像），可跳过大部分安装步骤。

---

## 五、网络要求

- 后端需访问 **OpenAI 兼容的 LLM API**（如 api.openai.com 或国内代理）
  - 如果服务器无法直接访问 OpenAI，需要配置代理或使用国内兼容接口（如 DeepSeek、智谱 GLM）
- 前端通过 Nginx 在 **80/443 端口**对外提供服务
- WebSocket 路径 `/ws/` 需要 Nginx 正确配置 `Upgrade` 头（项目已有 nginx.conf）

---

## 六、部署方式（Docker 一键）

```bash
# 1. 克隆项目
git clone git@github.com:lvzhuojun/voice-chat-assistant.git
cd voice-chat-assistant

# 2. 配置环境变量
cp .env.example .env
vim .env   # 填写 JWT_SECRET_KEY、DATABASE_URL、LLM_API_KEY 等

# 3. 克隆 GPT-SoVITS 源码
git clone https://github.com/RVC-Boss/GPT-SoVITS.git GPT_SoVITS

# 4. 下载预训练模型
conda activate voice-chat
python setup/download_models.py

# 5. 应用数据库迁移
alembic -c backend/alembic/alembic.ini upgrade head

# 6. 一键启动（含 Postgres + Redis + 后端 + 前端 + Nginx）
docker compose -f docker/docker-compose.yml up -d
```

启动后访问 `http://<服务器IP>` 即可使用。

---

## 七、推荐租用平台（国内）

### AutoDL（autodl.com）— 最推荐用于 ML 项目

- 按小时计费，价格透明
- 镜像预装 CUDA + conda + PyTorch，开箱即用
- 有磁盘快照，关机后数据保留
- 推荐配置：

| GPU | VRAM | 参考价格 | 备注 |
|-----|------|---------|------|
| RTX 3080 | 10 GB | ~¥1.5/小时 | 够用，性价比高 |
| RTX 3090 | 24 GB | ~¥2–2.5/小时 | 宽裕，推荐 |
| RTX 4090 | 24 GB | ~¥3–4/小时 | 最快，演示首选 |

> 演示或开发阶段按需开机，不用时关机，成本低。

### 其他选项

| 平台 | 特点 |
|------|------|
| 阿里云 PAI / 腾讯云 HAI | 稳定但贵，适合生产 |
| Vast.ai / RunPod | 国际平台，价格低，但延迟高且需要科学上网 |
| 矩池云（matpool.com） | 国内，类似 AutoDL |

---

## 八、选机建议总结

| 需求 | 建议配置 |
|------|---------|
| **演示 / 面试用** | AutoDL RTX 3090，按需开机，约 ¥2/小时 |
| **长期跑着** | AutoDL RTX 3080 包月，或阿里云/腾讯云 GPU 实例 |
| **预算有限** | AutoDL RTX 3080（10 GB），只跑 GPT-SoVITS，不装 CosyVoice |
| **想同时跑两个 TTS** | RTX 3090 / 4090（24 GB）有余量 |

最低可行配置：**RTX 3080（10 GB VRAM）+ 16 GB RAM + 40 GB 磁盘 + Ubuntu 22.04**
