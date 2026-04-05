"""
下载 GPT-SoVITS 预训练模型，并创建运行时所需目录结构。

运行方式（从项目根目录）：
    python setup/download_models.py
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path

# ── 目标目录 ────────────────────────────────────────────────────────────────
PRETRAINED_DIR = Path("storage/pretrained_models/GPT-SoVITS")
GPTSOVITS_SRC = Path("GPT-SoVITS/GPT_SoVITS")   # GPT-SoVITS 源码根
GPT_SOVITS_ALIAS = Path("GPT_SoVITS")             # 项目根下的别名目录

# ── HuggingFace 预训练模型 ───────────────────────────────────────────────────
HF_MODELS = [
    {
        "name": "chinese-hubert-base",
        "repo_id": "TencentGameMate/chinese-hubert-base",
        "local_dir": PRETRAINED_DIR / "chinese-hubert-base",
        "description": "中文 HuBERT 基础模型（TTS 音色匹配）",
    },
    {
        "name": "chinese-roberta-wwm-ext-large",
        "repo_id": "hfl/chinese-roberta-wwm-ext-large",
        "local_dir": PRETRAINED_DIR / "chinese-roberta-wwm-ext-large",
        "description": "中文 RoBERTa 大模型（文本编码）",
    },
]


def download_hf_model(model_info: dict) -> bool:
    """从 HuggingFace 下载单个模型。"""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("[ERROR] 未找到 huggingface_hub，请先安装：pip install huggingface_hub")
        return False

    name = model_info["name"]
    repo_id = model_info["repo_id"]
    local_dir = model_info["local_dir"]

    print(f"\n[INFO] 下载 {name}")
    print(f"       {model_info['description']}")
    print(f"       来源：https://huggingface.co/{repo_id}")
    print(f"       目标：{local_dir}")

    if local_dir.exists() and any(local_dir.iterdir()):
        print(f"[SKIP] {name} 已存在，跳过下载")
        return True

    try:
        local_dir.mkdir(parents=True, exist_ok=True)
        snapshot_download(repo_id=repo_id, local_dir=str(local_dir))
        print(f"[OK] {name} 下载完成")
        return True
    except Exception as e:
        print(f"[ERROR] 下载 {name} 失败: {e}")
        return False


def setup_g2pw_model() -> bool:
    """
    确保 G2PWModel 就位。
    优先使用 GPT-SoVITS 源码中已有的模型，否则解压 zip 包。
    最终模型路径：GPT-SoVITS/GPT_SoVITS/text/G2PWModel/
    """
    model_dir = GPTSOVITS_SRC / "text" / "G2PWModel"
    zip_path = GPTSOVITS_SRC / "text" / "G2PWModel_1.1.zip"

    if model_dir.exists() and any(model_dir.iterdir()):
        print(f"[SKIP] G2PWModel 已存在：{model_dir}")
        return True

    if zip_path.exists():
        print(f"[INFO] 解压 G2PWModel_1.1.zip ...")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(zip_path.parent)
            # 重命名解压目录（可能叫 G2PWModel_1.1）
            extracted = zip_path.parent / "G2PWModel_1.1"
            if extracted.exists() and not model_dir.exists():
                extracted.rename(model_dir)
            print(f"[OK] G2PWModel 解压完成：{model_dir}")
            return True
        except Exception as e:
            print(f"[ERROR] 解压失败：{e}")
            return False

    print(f"[WARN] 未找到 G2PWModel，TTS 首次运行时将尝试自动从 modelscope 下载")
    print(f"       （需要网络连接，可能较慢）")
    return True  # 非致命，TTS 会自动下载


def create_runtime_links() -> None:
    """
    在项目根目录创建 GPT_SoVITS/ 的运行时目录结构。
    GPT-SoVITS 内部代码使用 'GPT_SoVITS/...' 相对路径，
    因此需要 GPT_SoVITS/ 目录在项目根下可访问。
    """
    GPT_SOVITS_ALIAS.mkdir(exist_ok=True)

    links = {
        # GPT-SoVITS 默认 bert/hubert 路径回退到此目录
        GPT_SOVITS_ALIAS / "pretrained_models": PRETRAINED_DIR,
        # G2PW 模型路径（chinese2.py 硬编码 "GPT_SoVITS/text/G2PWModel"）
        GPT_SOVITS_ALIAS / "text": GPTSOVITS_SRC / "text",
    }

    for link_path, target in links.items():
        if not target.exists():
            print(f"[SKIP] 目标不存在，跳过链接：{target}")
            continue
        if link_path.exists() or link_path.is_symlink():
            continue  # 已存在，跳过

        if sys.platform == "win32":
            try:
                import subprocess
                subprocess.run(
                    ["cmd", "/c", "mklink", "/J",
                     str(link_path.absolute()),
                     str(target.absolute())],
                    check=True, capture_output=True
                )
                print(f"[OK] Junction 创建：{link_path} -> {target}")
            except Exception as e:
                print(f"[WARN] Junction 创建失败（{e}），尝试复制目录...")
                try:
                    shutil.copytree(target, link_path, dirs_exist_ok=True)
                    print(f"[OK] 目录已复制：{link_path}")
                except Exception as e2:
                    print(f"[ERROR] 复制失败：{e2}")
        else:
            try:
                link_path.symlink_to(target.absolute())
                print(f"[OK] 符号链接创建：{link_path} -> {target}")
            except Exception as e:
                print(f"[WARN] 符号链接失败（{e}），尝试复制...")
                try:
                    shutil.copytree(target, link_path, dirs_exist_ok=True)
                except Exception as e2:
                    print(f"[ERROR] 复制失败：{e2}")


def fix_lzma_windows() -> None:
    """
    Windows 特有：若 _lzma.pyd 在 conda 虚拟环境中缺失，
    从 base 环境复制（transformers / GPT-SoVITS 依赖 lzma）。
    """
    if sys.platform != "win32":
        return

    import importlib.util
    if importlib.util.find_spec("_lzma") is not None:
        return  # 已可用，无需修复

    env_dlls = Path(sys.prefix) / "DLLs"
    base_dlls = Path(sys.prefix).parent.parent / "DLLs"     # ../../../DLLs
    env_lib_bin = Path(sys.prefix) / "Library" / "bin"
    base_lib_bin = Path(sys.prefix).parent.parent / "Library" / "bin"

    fixed = False
    for src, dst in [
        (base_dlls / "_lzma.pyd", env_dlls / "_lzma.pyd"),
        (base_lib_bin / "liblzma.dll", env_lib_bin / "liblzma.dll"),
    ]:
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
                print(f"[OK] 已修复 lzma：{src.name} -> {dst}")
                fixed = True
            except Exception as e:
                print(f"[WARN] 复制 {src.name} 失败：{e}")

    if fixed:
        print("[INFO] lzma 修复完成，请重启 Python/服务使其生效")
    else:
        print("[WARN] 无法自动修复 _lzma，请手动安装：conda install -c conda-forge liblzma")


def check_existing() -> None:
    """显示已存在的模型状态。"""
    print("\n[INFO] 检查现有预训练模型...")
    for m in HF_MODELS:
        p = m["local_dir"]
        if p.exists() and any(p.iterdir()):
            size_mb = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1024 / 1024
            print(f"  [OK] {m['name']} ({size_mb:.1f} MB)")
        else:
            print(f"  [--] {m['name']} 未找到")

    g2pw = GPTSOVITS_SRC / "text" / "G2PWModel"
    status = "[OK]" if (g2pw.exists() and any(g2pw.iterdir())) else "[--]"
    print(f"  {status} G2PWModel")


def main() -> None:
    print("=" * 60)
    print(" GPT-SoVITS 预训练模型 & 运行时目录初始化")
    print("=" * 60)
    print(f"\n预训练模型目录：{PRETRAINED_DIR.absolute()}")

    # Step 0: 修复 Windows lzma 问题
    fix_lzma_windows()

    # Step 1: 检查现有状态
    check_existing()

    # Step 2: 确保目录存在
    PRETRAINED_DIR.mkdir(parents=True, exist_ok=True)

    # Step 3: 下载 HuggingFace 预训练模型
    print("\n[INFO] 下载 HuggingFace 预训练模型...")
    ok = sum(download_hf_model(m) for m in HF_MODELS)

    # Step 4: 处理 G2PWModel
    print("\n[INFO] 初始化 G2PWModel...")
    setup_g2pw_model()

    # Step 5: 创建运行时链接
    print("\n[INFO] 创建运行时目录链接...")
    create_runtime_links()

    # 汇总
    print("\n" + "=" * 60)
    print(f" 完成：{ok}/{len(HF_MODELS)} 个 HuggingFace 模型就绪")
    print("=" * 60)

    if ok < len(HF_MODELS):
        print("\n[WARN] 部分模型未就绪，TTS 功能可能受限")
        sys.exit(1)
    else:
        print("\n[OK] 所有预训练模型已就绪，可以启动服务")


if __name__ == "__main__":
    if not Path("environment.yml").exists():
        print("[ERROR] 请从项目根目录运行：python setup/download_models.py")
        sys.exit(1)
    main()
