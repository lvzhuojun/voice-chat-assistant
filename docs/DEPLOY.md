# Production Deployment Guide

> **Target environment:** Ubuntu 20.04 / 22.04 with an NVIDIA GPU.
> For local Windows development, see the [Quick Start](../README.md#quick-start) in the main README.

---

## Table of Contents

- [Server Requirements](#server-requirements)
- [Step-by-step Deployment](#step-by-step-deployment)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Configure Environment Variables](#2-configure-environment-variables)
  - [3. Clone GPT-SoVITS](#3-clone-gpt-sovits)
  - [4. Download Pretrained Models](#4-download-pretrained-models)
  - [5. Run Database Migrations](#5-run-database-migrations)
  - [6. Start with Docker Compose](#6-start-with-docker-compose)
  - [7. HTTPS (Recommended)](#7-https-recommended)
- [Importing Voice Models](#importing-voice-models)
- [Updating the Deployment](#updating-the-deployment)
- [Troubleshooting](#troubleshooting)

---

## Server Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Ubuntu 20.04 | Ubuntu 22.04 |
| CPU | 4 cores | 8 cores |
| RAM | 16 GB | 32 GB |
| GPU VRAM | 8 GB | 16 GB+ |
| CUDA | 12.8 | 12.8 |
| NVIDIA Driver | 545+ | latest stable |
| Docker | 24+ | latest |
| Docker Compose | v2 | latest |
| Disk | 40 GB | 80 GB+ |

---

## Step-by-step Deployment

### 1. Clone the Repository

```bash
git clone git@github.com:lvzhuojun/voice-chat-assistant.git
cd voice-chat-assistant
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
vim .env
```

Required fields to set:

```bash
# Strong random secret — generate with:
# openssl rand -hex 32
JWT_SECRET_KEY=<your-secret>

# Update password to something secure
DATABASE_URL=postgresql://voice:strongpassword@postgres:5432/voicechat

# Optional — leave empty for mock LLM responses
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

### 3. Clone GPT-SoVITS

```bash
git clone https://github.com/RVC-Boss/GPT-SoVITS.git GPT-SoVITS
```

### 4. Download Pretrained Models

```bash
conda activate voice-chat
python setup/download_models.py
```

Or copy from Project 1 if available:

```bash
cp -r ../voice-cloning-service/storage/pretrained_models/GPT-SoVITS/ \
       storage/pretrained_models/GPT-SoVITS/
```

Expected directory structure after this step:

```
storage/pretrained_models/GPT-SoVITS/
├── chinese-hubert-base/
└── chinese-roberta-wwm-ext-large/
```

### 5. Run Database Migrations

```bash
conda activate voice-chat
alembic upgrade head
```

### 6. Start with Docker Compose

```bash
docker compose -f docker/docker-compose.yml up -d
```

Check logs:

```bash
# All services
docker compose -f docker/docker-compose.yml logs -f

# Backend only
docker compose -f docker/docker-compose.yml logs -f backend
```

Verify services are healthy:

```bash
docker compose -f docker/docker-compose.yml ps
curl http://localhost:8000/api/health
```

### 7. HTTPS (Recommended)

```bash
# Install Certbot
apt install certbot python3-certbot-nginx

# Obtain a certificate (replace with your domain)
certbot --nginx -d yourdomain.com

# Then update docker/nginx/nginx.conf with your domain and cert paths
docker compose -f docker/docker-compose.yml restart frontend
```

---

## Importing Voice Models

After deployment, voice models can be imported via the web UI:

1. Open `https://yourdomain.com` and log in.
2. Navigate to **Voice Management**.
3. Upload the ZIP package produced by Project 1.

For CLI-based import or troubleshooting, see [VOICE_MODEL_IMPORT.md](VOICE_MODEL_IMPORT.md).

---

## Updating the Deployment

```bash
git pull

# Rebuild and restart only the affected services
docker compose -f docker/docker-compose.yml up -d --build backend frontend

# Run any new migrations
conda activate voice-chat
alembic upgrade head
```

---

## Troubleshooting

### CUDA is not available inside Docker

Run a quick sanity check:

```bash
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi
```

If it fails, install the NVIDIA Container Toolkit:

```bash
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list \
  | tee /etc/apt/sources.list.d/nvidia-docker.list
apt update && apt install -y nvidia-container-toolkit
systemctl restart docker
```

### TTS engine fails to load

Confirm that the pretrained model directories are present:

```bash
ls storage/pretrained_models/GPT-SoVITS/
# Expected: chinese-hubert-base  chinese-roberta-wwm-ext-large
```

If missing, re-run `python setup/download_models.py`.

### WebSocket connections are dropped by Nginx

Ensure `docker/nginx/nginx.conf` includes the upgrade headers for WebSocket locations:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

### Database migration errors on fresh deploy

If Alembic reports "relation already exists", the database may have been partially initialized. Drop and recreate:

```bash
docker compose -f docker/docker-compose.yml exec postgres \
  psql -U voice -c "DROP DATABASE voicechat; CREATE DATABASE voicechat;"
alembic upgrade head
```

> **Warning:** this deletes all data.
