# Voice Model Import Guide

This document explains how to import a voice model trained in **voice-cloning-service** (Project 1) into **voice-chat-assistant** (this project).

---

## Table of Contents

- [Output Structure from Project 1](#output-structure-from-project-1)
- [Method 1 — Web UI Upload (Recommended)](#method-1--web-ui-upload-recommended)
- [Method 2 — API Upload](#method-2--api-upload)
- [Notes and Constraints](#notes-and-constraints)
- [Backend Inference Reference](#backend-inference-reference)

---

## Output Structure from Project 1

After training completes in `voice-cloning-service`, each voice produces:

```
voice-cloning-service/
└── storage/
    └── models/
        └── {voice_id}/
            ├── {voice_id}_gpt.ckpt      # GPT model weights
            ├── {voice_id}_sovits.pth    # SoVITS model weights
            ├── metadata.json            # Training metadata
            └── reference.wav           # Reference audio (required for inference)
```

**`metadata.json` example:**

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

> `base_model_version` **must** be `"GPT-SoVITS v2"` — other versions are not supported.

---

## Method 1 — Web UI Upload (Recommended)

### Step 1: Pack the voice folder into a ZIP

The ZIP must have the four files **at the root** (no nested folders).

**Windows PowerShell:**

```powershell
$VOICE_ID = "550e8400-e29b-41d4-a716-446655440000"
Compress-Archive `
  -Path "storage/models/$VOICE_ID/*" `
  -DestinationPath "$VOICE_ID.zip"
```

**Linux / macOS:**

```bash
VOICE_ID="550e8400-e29b-41d4-a716-446655440000"
cd voice-cloning-service/storage/models/$VOICE_ID
zip -r ../../../../$VOICE_ID.zip .
```

Expected ZIP contents:

```
550e8400-....zip
├── 550e8400-..._gpt.ckpt
├── 550e8400-..._sovits.pth
├── metadata.json
└── reference.wav
```

### Step 2: Upload via the web interface

1. Open voice-chat-assistant and log in.
2. Click the menu → **Voice Management**.
3. Drag the ZIP onto the upload area, or click to browse.
4. Wait for validation and upload to complete (the server checks all four required files).
5. The new voice appears as a card in the grid.
6. Click **Set as Current** to use it in conversations.

---

## Method 2 — API Upload

Use this when the frontend is unavailable or you want to script imports.

```bash
VOICE_ID="550e8400-e29b-41d4-a716-446655440000"
JWT_TOKEN="eyJ..."

curl -X POST http://localhost:8000/api/voices/import \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "file=@${VOICE_ID}.zip"
```

On success, the server returns `201 Created` with the voice record. See [API.md](API.md#post-apivoicesimport) for the full response schema.

---

## Notes and Constraints

| Constraint | Detail |
|------------|--------|
| **`reference.wav` is required** | Used as the reference audio during inference — must be the original sample from training |
| **Model version** | Only `GPT-SoVITS v2` is supported (`base_model_version` field in `metadata.json`) |
| **Pretrained models** | `chinese-hubert-base` and `chinese-roberta-wwm-ext-large` must be present in `storage/pretrained_models/GPT-SoVITS/` — run `python setup/download_models.py` if missing |
| **VRAM limit** | TTS engine keeps at most 3 voice models in GPU memory (LRU eviction) |
| **File size** | A complete voice ZIP is typically 300 MB – 1 GB; allow time for upload on slow connections |

---

## Backend Inference Reference

The TTS engine loads each voice model as follows:

```python
from TTS_infer_pack.TTS import TTS, TTS_Config

voice_id = "550e8400-e29b-41d4-a716-446655440000"
user_id  = "1"
model_dir = f"storage/voice_models/{user_id}/{voice_id}"

config = TTS_Config({
    "custom": {
        "device": "cuda",
        "is_half": True,
        "version": "v2",
        "t2s_weights_path":    f"{model_dir}/{voice_id}_gpt.ckpt",
        "vits_weights_path":   f"{model_dir}/{voice_id}_sovits.pth",
        "cnhuhbert_base_path": "storage/pretrained_models/GPT-SoVITS/chinese-hubert-base",
        "bert_base_path":      "storage/pretrained_models/GPT-SoVITS/chinese-roberta-wwm-ext-large",
    }
})
tts = TTS(config)

# Inference (reference.wav must be provided)
import soundfile as sf

result = tts.run({
    "text":               "你好，这是测试",
    "text_lang":          "zh",
    "ref_audio_path":     f"{model_dir}/reference.wav",
    "prompt_lang":        "zh",
    "prompt_text":        "",
    "top_k":              5,
    "top_p":              1.0,
    "temperature":        1.0,
    "text_split_method":  "cut5",
    "batch_size":         1,
    "speed_factor":       1.0,
    "fragment_interval":  0.3,
    "streaming_mode":     False,
    "seed":               -1,
    "parallel_infer":     True,
    "repetition_penalty": 1.35,
})

for sample_rate, audio_data in result:
    sf.write("output.wav", audio_data, sample_rate)
```
