# 音色模型导入指南

本文档说明如何将 **voice-cloning-service**（项目一）训练好的音色模型导入到 **voice-chat-assistant**（本项目）使用。

## 项目一输出的文件结构

在 voice-cloning-service 中，每个音色训练完成后会产出：

```
voice-cloning-service/
└── storage/
    └── models/
        └── {voice_id}/
            ├── {voice_id}_gpt.ckpt        # GPT 模型权重
            ├── {voice_id}_sovits.pth      # SoVITS 模型权重
            ├── metadata.json              # 训练元数据
            └── reference.wav             # 参考音频（推理必须）
```

### metadata.json 示例

```json
{
  "voice_id": "550e8400-e29b-41d4-a716-446655440000",
  "voice_name": "My Voice",
  "language": "zh",
  "created_at": "2024-01-01T00:00:00Z",
  "training_epochs_gpt": 15,
  "training_epochs_sovits": 8,
  "gpt_model_file": "550e8400-e29b-41d4-a716-446655440000_gpt.ckpt",
  "sovits_model_file": "550e8400-e29b-41d4-a716-446655440000_sovits.pth",
  "base_model_version": "GPT-SoVITS v2"
}
```

## 导入方法一：通过 Web 界面上传（推荐）

### 1. 打包音色文件为 ZIP

在 voice-cloning-service 目录中执行：

```bash
# Windows PowerShell
$VOICE_ID = "你的voice_id"
Compress-Archive -Path "storage/models/$VOICE_ID/*" -DestinationPath "$VOICE_ID.zip"

# Linux/Mac
VOICE_ID="你的voice_id"
cd storage/models/$VOICE_ID
zip -r ../../$VOICE_ID.zip .
```

ZIP 内部结构必须如下（**直接在根目录，不要嵌套文件夹**）：

```
your_voice.zip
├── {voice_id}_gpt.ckpt
├── {voice_id}_sovits.pth
├── metadata.json
└── reference.wav
```

### 2. 在 Web 界面导入

1. 打开 voice-chat-assistant，登录账号
2. 点击左上角菜单 → **音色管理**
3. 将 ZIP 文件拖拽到虚线上传区，或点击选择文件
4. 等待上传和验证完成（会检查四个必要文件）
5. 导入成功后，在卡片网格中可见新音色
6. 点击**设为当前**即可在对话中使用该音色

## 导入方法二：手动复制文件

如果前端不可用，可以直接复制文件：

```bash
# 1. 在本项目创建目录
mkdir -p storage/voice_models/{user_id}/{voice_id}

# 2. 从项目一复制四个文件
cp ../voice-cloning-service/storage/models/{voice_id}/{voice_id}_gpt.ckpt \
   storage/voice_models/{user_id}/{voice_id}/

cp ../voice-cloning-service/storage/models/{voice_id}/{voice_id}_sovits.pth \
   storage/voice_models/{user_id}/{voice_id}/

cp ../voice-cloning-service/storage/models/{voice_id}/metadata.json \
   storage/voice_models/{user_id}/{voice_id}/

cp ../voice-cloning-service/storage/models/{voice_id}/reference.wav \
   storage/voice_models/{user_id}/{voice_id}/

# 3. 通过 API 注册到数据库（上传 ZIP 包）
curl -X POST http://localhost:8000/api/voices/import \
  -H "Authorization: Bearer {jwt_token}" \
  -F "file=@{voice_id}.zip"
```

## 推理加载方式（后端实现参考）

本项目 TTS 引擎严格按照以下方式加载模型（与项目一一致）：

```python
from TTS_infer_pack.TTS import TTS, TTS_Config

voice_id = "550e8400-e29b-41d4-a716-446655440000"
user_id = "1"
model_dir = f"storage/voice_models/{user_id}/{voice_id}"

config = TTS_Config({
    "custom": {
        "device": "cuda",
        "is_half": True,
        "version": "v2",
        "t2s_weights_path": f"{model_dir}/{voice_id}_gpt.ckpt",
        "vits_weights_path": f"{model_dir}/{voice_id}_sovits.pth",
        "cnhuhbert_base_path": "storage/pretrained_models/GPT-SoVITS/chinese-hubert-base",
        "bert_base_path": "storage/pretrained_models/GPT-SoVITS/chinese-roberta-wwm-ext-large",
    }
})
tts = TTS(config)

# 推理（必须传入 reference.wav）
import soundfile as sf
ref_audio_path = f"{model_dir}/reference.wav"

result_generator = tts.run({
    "text": "你好，这是测试",
    "text_lang": "zh",
    "ref_audio_path": ref_audio_path,
    "prompt_lang": "zh",
    "prompt_text": "",
    "top_k": 5,
    "top_p": 1.0,
    "temperature": 1.0,
    "text_split_method": "cut5",
    "batch_size": 1,
    "speed_factor": 1.0,
    "fragment_interval": 0.3,
    "streaming_mode": False,
    "seed": -1,
    "parallel_infer": True,
    "repetition_penalty": 1.35,
})

for sr, audio_data in result_generator:
    sf.write("output.wav", audio_data, sr)
```

## 注意事项

1. **reference.wav 不可缺少**：这是推理时的参考音色，必须是训练时使用的原始参考音频
2. **模型版本**：本项目只支持 `GPT-SoVITS v2`，`base_model_version` 字段必须为 `"GPT-SoVITS v2"`
3. **预训练模型**：需要提前下载 `chinese-hubert-base` 和 `chinese-roberta-wwm-ext-large` 到 `storage/pretrained_models/GPT-SoVITS/`，运行 `python setup/download_models.py`
4. **VRAM 限制**：TTS 引擎使用 LRU 缓存，最多同时加载 3 个音色模型，避免 VRAM 溢出
5. **文件大小**：完整音色包（包含模型权重）通常 300MB~1GB，上传时请耐心等待
