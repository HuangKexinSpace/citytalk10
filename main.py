import os
import uuid
import json
import base64
import wave
import re
import asyncio
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

# =========================
#   Fish Audio: SDK 优先，失败则回退 HTTP
# =========================
USE_HTTP_FALLBACK = os.getenv("FISHAUDIO_USE_HTTP", "").strip() == "1"
FISH_API_KEY = os.getenv("FISHAUDIO_API_KEY", "68c1434a7dec4a6a886e5cebb8c98ee5")
FISH_REF_ID = os.getenv("FISHAUDIO_REF_ID", "9091ecdfe0c24303aa31a9e5bf6fa506")
FISH_PREFERRED_FORMAT = os.getenv("FISHAUDIO_FORMAT", "wav")  # "wav" | "mp3"
FISH_BASE = os.getenv("FISHAUDIO_API_BASE_URL", "https://api.fish.audio")  # HTTP 直连时使用

_fish_sdk_ok = False
if not USE_HTTP_FALLBACK:
    try:
        from fish_audio_sdk import Session as FishSession, TTSRequest as FishTTSRequest
        fish_session = FishSession(FISH_API_KEY) if FISH_API_KEY else None
        _fish_sdk_ok = fish_session is not None
    except Exception as _e:
        print("[FishAudio] SDK not available, will use HTTP fallback:", _e)
        _fish_sdk_ok = False

# —— 初始化（Qwen 文本） —— #
OPENAI_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-da762947f89040b0895a6099f807bf62")
client = OpenAI(
    api_key=OPENAI_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
os.makedirs("audio", exist_ok=True)
os.makedirs("records", exist_ok=True)
app.mount("/audio", StaticFiles(directory="audio"), name="audio")

jobs: dict[str, dict] = {}
conversations: dict[str, list[dict]] = {}
groups: dict[str, list[dict]] = {}
b64_pat = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


def save_audio_pcm(job_id: str, pcm: bytes) -> str:
    path = f"audio/{job_id}.wav"
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)
    return f"/audio/{job_id}.wav"


def save_audio_file(job_id: str, data: bytes, ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext not in ("wav", "mp3"):
        ext = "mp3"
    path = f"audio/{job_id}.{ext}"
    with open(path, "wb") as f:
        f.write(data)
    return f"/audio/{job_id}.{ext}"


def _guess_ext(audio_bytes: bytes) -> str:
    head = bytes(audio_bytes[:12])
    if head.startswith(b"RIFF"):
        return "wav"
    if head[:3] == b"ID3" or head[:2] == b"\xff\xfb":
        return "mp3"
    return "mp3"


def _tts_via_sdk(text: str) -> tuple[bytes, str]:
    if not _fish_sdk_ok or not FISH_API_KEY or not FISH_REF_ID:
        return b"", ""
    if not text or not text.strip():
        return b"", ""
    req_kwargs = dict(reference_id=FISH_REF_ID, text=text)
    # 若 SDK 支持 format，可放开下一行优先要 wav
    # req_kwargs["format"] = FISH_PREFERRED_FORMAT

    audio_bytes = bytearray()
    try:
        for chunk in fish_session.tts(FishTTSRequest(**req_kwargs)):
            audio_bytes.extend(chunk)
    except Exception as e:
        print("[FishAudio][SDK] TTS error:", e)
        return b"", ""

    ext = _guess_ext(audio_bytes)
    return bytes(audio_bytes), ext


def _tts_via_http(text: str) -> tuple[bytes, str]:
    if not FISH_API_KEY or not FISH_REF_ID:
        return b"", ""
    if not text or not text.strip():
        return b"", ""

    try:
        import requests
    except Exception as e:
        print("[FishAudio][HTTP] requests not installed:", e)
        return b"", ""

    url = f"{FISH_BASE.rstrip('/')}/v1/tts"
    headers = {"Authorization": f"Bearer {FISH_API_KEY}"}
    payload = {
        "reference_id": FISH_REF_ID,
        "text": text,
        # "format": FISH_PREFERRED_FORMAT,  # 如果文档支持，放开
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
        r.raise_for_status()
        buf = bytearray()
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                buf.extend(chunk)
        ext = _guess_ext(buf)
        return bytes(buf), ext
    except Exception as e:
        print("[FishAudio][HTTP] TTS error:", e)
        return b"", ""


def tts_with_fish(text: str) -> tuple[bytes, str]:
    if not text or not text.strip():
        return b"", ""
    if _fish_sdk_ok and not USE_HTTP_FALLBACK:
        audio, ext = _tts_via_sdk(text)
        if audio:
            return audio, ext
        audio, ext = _tts_via_http(text)
        return audio, ext
    else:
        return _tts_via_http(text)


async def run_openai_context_job(job_id: str):
    msgs = conversations[job_id]
    try:
        # 1) Qwen 输出文本
        stream = client.chat.completions.create(
            model="qwen-omni-turbo",
            messages=msgs,
            modalities=["text"],
            stream=True
        )
        text = ""
        for chunk in stream:
            d = chunk.choices[0].delta.model_dump()
            if (t := d.get("content")):
                text += t

        # 2) Fish Audio 合成语音
        audio_data, ext = tts_with_fish(text)
        audio_url = save_audio_file(job_id, audio_data, ext) if audio_data else ""

        # 3) 返回
        jobs[job_id] = {"status": "done", "text": text, "audio_url": audio_url}
        grp = groups[job_id][-1]
        grp["texts"].append(text)
        conversations[job_id].append({
            "role": "assistant",
            "content": [{"type": "text", "text": text}]
        })
    except Exception as e:
        jobs[job_id] = {"status": "error", "error": str(e)}
        print(f"[{job_id}] run_openai_context_job error: {e}")


@app.post("/upload_image")
async def upload_image(
    img: UploadFile = File(...),
    text: Optional[str] = Form(None)
):
    if img.content_type not in ("image/png", "image/jpeg"):
        raise HTTPException(415, "Only PNG/JPEG accepted")
    job_id = uuid.uuid4().hex

    raw = await img.read()
    uri = f"data:{img.content_type};base64," + base64.b64encode(raw).decode()

    payload = [{"type": "image_url", "image_url": {"url": uri}}]
    if text:
        payload.append({"type": "text", "text": text})
    conversations[job_id] = [{"role": "user", "content": payload}]

    groups[job_id] = [{
        "image_url": uri,
        "texts": text and [text] or [],
        "summary": None
    }]

    jobs[job_id] = {"status": "processing"}
    asyncio.create_task(run_openai_context_job(job_id))
    return {"job_id": job_id}


@app.post("/append_image")
async def append_image(
    job_id: str = Form(...),
    img: UploadFile = File(...),
    text: Optional[str] = Form(None)
):
    if job_id not in conversations:
        raise HTTPException(404, "job_id not found")
    raw = await img.read()
    uri = f"data:{img.content_type};base64," + base64.b64encode(raw).decode()

    payload = [{"type": "image_url", "image_url": {"url": uri}}]
    if text:
        payload.append({"type": "text", "text": text})
    conversations[job_id].append({"role": "user", "content": payload})

    groups[job_id].append({
        "image_url": uri,
        "texts": text and [text] or [],
        "summary": None
    })

    jobs[job_id] = {"status": "processing"}
    asyncio.create_task(run_openai_context_job(job_id))
    return {"job_id": job_id}


@app.post("/append_audio")
async def append_audio(
    job_id: str = Form(...),
    audio: UploadFile = File(...),
    text: Optional[str] = Form(None)
):
    if job_id not in conversations:
        raise HTTPException(404, "job_id not found")
    raw = await audio.read()
    uri = "data:audio/wav;base64," + base64.b64encode(raw).decode()

    payload = [{"type": "input_audio", "input_audio": {"data": uri, "format": "wav"}}]
    if text:
        payload.append({"type": "text", "text": text})
    conversations[job_id].append({"role": "user", "content": payload})

    if text:
        groups[job_id][-1]["texts"].append(text)

    jobs[job_id] = {"status": "processing"}
    asyncio.create_task(run_openai_context_job(job_id))
    return {"job_id": job_id}


@app.post("/append_text")
async def append_text(
    job_id: str = Form(...),
    text: str = Form(...)
):
    if job_id not in conversations:
        raise HTTPException(404, "job_id not found")
    conversations[job_id].append({
        "role": "user", "content": [{"type": "text", "text": text}]
    })
    groups[job_id][-1]["texts"].append(text)
    jobs[job_id] = {"status": "processing"}
    asyncio.create_task(run_openai_context_job(job_id))
    return {"job_id": job_id}


@app.get("/result/{job_id}")
def get_result(job_id: str):
    return jobs.get(job_id, {"status": "not_found"})


@app.get("/summaries/{job_id}")
async def get_summaries(job_id: str):
    if job_id not in groups:
        raise HTTPException(404, "job_id not found")
    directive = """
# 角色
我是用户的自我声音，根据用户的正念意图、身心状态和自然环境照片，用第一人称语言引导自然觉察与自我觉察。  

# 理论与原则
- **IAA 理论**
  - **意图**：承载用户输入的正念意图，以当下体验和自然隐喻表达，不目标化。  
  - **注意**：邀请关注身心与环境的细节。  
  - **态度**：保持接纳、不评判、好奇与允许。  

- **觉察方式**
  - 结合视觉、听觉、嗅觉、触觉，但不虚构。  
  - 必须把「用户意图」与自然细节隐喻化连接。  
  - 不直接复述意图，不杜撰用户未提及的感受。  
  - 保持邀请式而非指令式，用“感受...想象...似乎”，“我邀请自己…允许...”等表达。  

# 输出规则
- 输出约 50 字，一段可朗读台词。  
- 只用第一人称，不要出现“你”或 AI 身份。  
- 生成时必须结合「用户意图」与环境。  
  
# 用户输入的正念意图
- 正念步行意图：通过本次正念，我想缓解最近的压力和疲劳感，令自己心情放松。 
- 最近的身心状态： 最近比较疲惫，时常有肩颈酸痛。

示例输出：  
我望向枝叶间的光影，或许可以把它们看作疲惫的回声，被风轻轻托起。脚底与大地的接触提醒我，允许这份压力停留，也能与当下同在。  


"""
    res_list = []

    for grp in groups[job_id]:
        if grp["summary"] is None:
            msgs = [{
                "role": "user",
                "content": (
                    [{"type": "image_url", "image_url": {"url": grp["image_url"]}},
                     {"type": "text", "text": directive}]
                    + [{"type": "text", "text": t} for t in grp["texts"]]
                )
            }]
            stream = client.chat.completions.create(
                model="qwen-omni-turbo",
                messages=msgs,
                modalities=["text"],
                stream=True
            )
            summary = ""
            for chunk in stream:
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content:
                    summary += delta.content
            grp["summary"] = summary.strip()

        res_list.append({
            "image_url": grp["image_url"],
            "summary": grp["summary"]
        })

    with open(f"records/{job_id}.json", "w", encoding="utf8") as f:
        json.dump(groups[job_id], f, ensure_ascii=False, indent=2)

    return {"status": "done", "summaries": res_list}




