"""
下载 GPT-SoVITS 预训练模型脚本
下载 chinese-hubert-base 和 chinese-roberta-wwm-ext-large
使用 HuggingFace 官方源（适合美国网络环境）
"""

import os
import sys
from pathlib import Path

# 目标目录
PRETRAINED_DIR = Path("storage/pretrained_models/GPT-SoVITS")

# 需要下载的模型
MODELS = [
    {
        "name": "chinese-hubert-base",
        "repo_id": "TencentGameMate/chinese-hubert-base",
        "local_dir": PRETRAINED_DIR / "chinese-hubert-base",
        "description": "中文 HuBERT 基础模型（STT 特征提取）",
    },
    {
        "name": "chinese-roberta-wwm-ext-large",
        "repo_id": "hfl/chinese-roberta-wwm-ext-large",
        "local_dir": PRETRAINED_DIR / "chinese-roberta-wwm-ext-large",
        "description": "中文 RoBERTa 大模型（文本编码）",
    },
]


def download_model(model_info: dict) -> bool:
    """
    从 HuggingFace 下载单个模型。

    Args:
        model_info: 包含 repo_id、local_dir 等信息的字典

    Returns:
        bool: 下载是否成功
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("[ERROR] 未找到 huggingface_hub，请先安装：pip install huggingface_hub")
        return False

    name = model_info["name"]
    repo_id = model_info["repo_id"]
    local_dir = model_info["local_dir"]
    description = model_info["description"]

    print(f"\n[INFO] 下载 {name}")
    print(f"       {description}")
    print(f"       来源：https://huggingface.co/{repo_id}")
    print(f"       目标：{local_dir}")

    # 检查是否已存在
    if local_dir.exists() and any(local_dir.iterdir()):
        print(f"[SKIP] {name} 已存在，跳过下载")
        return True

    try:
        local_dir.mkdir(parents=True, exist_ok=True)
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(local_dir),
            # 使用官方源（美国网络直接访问）
            endpoint="https://huggingface.co",
        )
        print(f"[SUCCESS] {name} 下载完成")
        return True
    except Exception as e:
        print(f"[ERROR] 下载 {name} 失败: {e}")
        return False


def check_existing_models() -> None:
    """检查并显示已存在的模型状态。"""
    print("\n[INFO] 检查现有预训练模型...")
    for model_info in MODELS:
        local_dir = model_info["local_dir"]
        if local_dir.exists() and any(local_dir.iterdir()):
            files = list(local_dir.rglob("*"))
            size_mb = sum(f.stat().st_size for f in files if f.is_file()) / 1024 / 1024
            print(f"  ✓ {model_info['name']} ({size_mb:.1f} MB)")
        else:
            print(f"  ✗ {model_info['name']} 未下载")


def main() -> None:
    """主函数：下载所有预训练模型。"""
    print("=" * 60)
    print(" GPT-SoVITS 预训练模型下载")
    print("=" * 60)
    print(f"\n下载目录：{PRETRAINED_DIR.absolute()}")

    # 确保目录存在
    PRETRAINED_DIR.mkdir(parents=True, exist_ok=True)

    # 检查现有状态
    check_existing_models()

    print("\n[INFO] 开始下载...")

    success_count = 0
    for model_info in MODELS:
        if download_model(model_info):
            success_count += 1

    print("\n" + "=" * 60)
    print(f" 完成：{success_count}/{len(MODELS)} 个模型下载成功")
    print("=" * 60)

    if success_count < len(MODELS):
        print("\n[WARNING] 部分模型下载失败，TTS 功能可能无法使用")
        sys.exit(1)
    else:
        print("\n[SUCCESS] 所有预训练模型已就绪")
        print("\n提示：如果你有 voice-cloning-service，也可以直接复制：")
        print("  cp -r ../voice-cloning-service/storage/pretrained_models/GPT-SoVITS/ \\")
        print("    storage/pretrained_models/GPT-SoVITS/")


if __name__ == "__main__":
    # 确保从项目根目录运行
    if not Path("environment.yml").exists():
        print("[ERROR] 请从项目根目录运行此脚本：python setup/download_models.py")
        sys.exit(1)

    main()
