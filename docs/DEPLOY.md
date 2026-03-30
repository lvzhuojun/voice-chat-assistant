# 生产环境部署指南（Linux 服务器）

## 服务器要求

- Ubuntu 20.04 / 22.04
- CUDA 12.8+，NVIDIA 驱动 545+
- 至少 16GB RAM，8GB VRAM（RTX 5060 或更好）
- Docker 24+，Docker Compose v2

## 部署步骤

### 1. 克隆项目

```bash
git clone git@github.com:lvzhuojun/voice-chat-assistant.git
cd voice-chat-assistant
```

### 2. 配置环境变量

```bash
cp .env.example .env
vim .env

# 必须修改：
# DATABASE_URL=postgresql://voice:strongpassword@postgres:5432/voicechat
# JWT_SECRET_KEY=$(openssl rand -hex 32)
# LLM_API_KEY=sk-...（可选，为空时 mock）
```

### 3. 克隆 GPT-SoVITS

```bash
git clone https://github.com/RVC-Boss/GPT-SoVITS.git GPT-SoVITS
```

### 4. 下载预训练模型

```bash
conda activate voice-chat
python setup/download_models.py
```

或从项目一复制：

```bash
cp -r ../voice-cloning-service/storage/pretrained_models/GPT-SoVITS/ \
  storage/pretrained_models/GPT-SoVITS/
```

### 5. 运行数据库迁移

```bash
conda activate voice-chat
cd backend
alembic upgrade head
```

### 6. Docker 部署

```bash
docker compose -f docker/docker-compose.yml up -d
```

查看日志：

```bash
docker compose -f docker/docker-compose.yml logs -f backend
```

### 7. 配置 HTTPS（可选，推荐生产使用）

```bash
# 安装 Certbot
apt install certbot python3-certbot-nginx

# 申请证书（替换为你的域名）
certbot --nginx -d yourdomain.com

# 修改 docker/nginx/nginx.conf 中的域名和证书路径
```

## 导入音色

部署完成后，通过 Web 界面的音色管理页面上传 ZIP 包，或参考 [VOICE_MODEL_IMPORT.md](VOICE_MODEL_IMPORT.md)。

## 更新部署

```bash
git pull
docker compose -f docker/docker-compose.yml up -d --build backend frontend
```

## 常见问题

**Q: CUDA 不可用？**

```bash
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi
```

如果报错，检查 NVIDIA Container Toolkit：

```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list \
  | tee /etc/apt/sources.list.d/nvidia-docker.list
apt update && apt install -y nvidia-container-toolkit
systemctl restart docker
```

**Q: TTS 加载失败？**

确认 GPT-SoVITS 目录完整，且预训练模型已下载：

```bash
ls storage/pretrained_models/GPT-SoVITS/
# 应该有 chinese-hubert-base/ 和 chinese-roberta-wwm-ext-large/
```

**Q: WebSocket 连接失败？**

检查 nginx.conf 中 WebSocket upgrade 配置是否正确（proxy_http_version 1.1 + Upgrade/Connection headers）。
