# import os
# import uuid
# import json
# import base64
# import wave
# import re
# import asyncio
# from typing import Optional

# from fastapi import FastAPI, UploadFile, File, Form, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from openai import OpenAI

# # —— 初始化 —— #
# OPENAI_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-da762947f89040b0895a6099f807bf62")
# client = OpenAI(
#     api_key=OPENAI_KEY,
#     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
# )

# app = FastAPI()
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
# )
# os.makedirs("audio", exist_ok=True)
# os.makedirs("records", exist_ok=True)
# app.mount("/audio", StaticFiles(directory="audio"), name="audio")

# jobs: dict[str, dict] = {}
# conversations: dict[str, list[dict]] = {}
# groups: dict[str, list[dict]] = {}
# b64_pat = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


# def save_audio_pcm(job_id: str, pcm: bytes) -> str:
#     path = f"audio/{job_id}.wav"
#     with wave.open(path, "wb") as w:
#         w.setnchannels(1)
#         w.setsampwidth(2)
#         w.setframerate(24000)
#         w.writeframes(pcm)
#     return f"/audio/{job_id}.wav"


# async def run_openai_context_job(job_id: str):
#     msgs = conversations[job_id]
#     try:
#         stream = client.chat.completions.create(
#             model="qwen-omni-turbo",
#             messages=msgs,
#             modalities=["text", "audio"],
#             audio={"voice": "Chelsie", "format": "wav"},
#             stream=True
#         )
#         text, pcm = "", b""
#         for chunk in stream:  # 同步迭代
#             d = chunk.choices[0].delta.model_dump()
#             if (t := d.get("content")):
#                 text += t
#             audio_field = d.get("audio")
#             if isinstance(audio_field, dict):
#                 if (tt := audio_field.get("text") or audio_field.get("transcript")):
#                     text += tt
#                 piece = audio_field.get("data")
#             elif isinstance(audio_field, str):
#                 piece = audio_field
#             else:
#                 piece = None
#             if piece and b64_pat.match(piece):
#                 try:
#                     pcm += base64.b64decode(piece)
#                 except:
#                     pass

#         wav_url = save_audio_pcm(job_id, pcm) if pcm else ""
#         jobs[job_id] = {"status": "done", "text": text, "audio_url": wav_url}

#         grp = groups[job_id][-1]
#         grp["texts"].append(text)

#         conversations[job_id].append({
#             "role": "assistant",
#             "content": [{"type": "text", "text": text}]
#         })

#     except Exception as e:
#         jobs[job_id] = {"status": "error", "error": str(e)}
#         print(f"[{job_id}] run_openai_context_job error: {e}")


# @app.post("/upload_image")
# async def upload_image(
#     img: UploadFile = File(...),
#     text: Optional[str] = Form(None)
# ):
#     if img.content_type not in ("image/png", "image/jpeg"):
#         raise HTTPException(415, "Only PNG/JPEG accepted")
#     job_id = uuid.uuid4().hex

#     raw = await img.read()
#     uri = f"data:{img.content_type};base64," + base64.b64encode(raw).decode()

#     payload = [{"type": "image_url", "image_url": {"url": uri}}]
#     if text:
#         payload.append({"type": "text", "text": text})
#     conversations[job_id] = [{"role": "user", "content": payload}]

#     groups[job_id] = [{
#         "image_url": uri,
#         "texts": text and [text] or [],
#         "summary": None
#     }]

#     jobs[job_id] = {"status": "processing"}
#     asyncio.create_task(run_openai_context_job(job_id))
#     return {"job_id": job_id}


# @app.post("/append_image")
# async def append_image(
#     job_id: str = Form(...),
#     img: UploadFile = File(...),
#     text: Optional[str] = Form(None)
# ):
#     if job_id not in conversations:
#         raise HTTPException(404, "job_id not found")
#     raw = await img.read()
#     uri = f"data:{img.content_type};base64," + base64.b64encode(raw).decode()

#     payload = [{"type": "image_url", "image_url": {"url": uri}}]
#     if text:
#         payload.append({"type": "text", "text": text})
#     conversations[job_id].append({"role": "user", "content": payload})

#     groups[job_id].append({
#         "image_url": uri,
#         "texts": text and [text] or [],
#         "summary": None
#     })

#     jobs[job_id] = {"status": "processing"}
#     asyncio.create_task(run_openai_context_job(job_id))
#     return {"job_id": job_id}


# @app.post("/append_audio")
# async def append_audio(
#     job_id: str = Form(...),
#     audio: UploadFile = File(...),
#     text: Optional[str] = Form(None)
# ):
#     if job_id not in conversations:
#         raise HTTPException(404, "job_id not found")
#     raw = await audio.read()
#     uri = "data:audio/wav;base64," + base64.b64encode(raw).decode()

#     payload = [{"type": "input_audio", "input_audio": {"data": uri, "format": "wav"}}]
#     if text:
#         payload.append({"type": "text", "text": text})
#     conversations[job_id].append({"role": "user", "content": payload})

#     if text:
#         groups[job_id][-1]["texts"].append(text)

#     jobs[job_id] = {"status": "processing"}
#     asyncio.create_task(run_openai_context_job(job_id))
#     return {"job_id": job_id}


# @app.post("/append_text")
# async def append_text(
#     job_id: str = Form(...),
#     text: str = Form(...)
# ):
#     if job_id not in conversations:
#         raise HTTPException(404, "job_id not found")
#     conversations[job_id].append({
#         "role": "user", "content": [{"type": "text", "text": text}]
#     })
#     groups[job_id][-1]["texts"].append(text)
#     jobs[job_id] = {"status": "processing"}
#     asyncio.create_task(run_openai_context_job(job_id))
#     return {"job_id": job_id}


# @app.get("/result/{job_id}")
# def get_result(job_id: str):
#     return jobs.get(job_id, {"status": "not_found"})


# @app.get("/summaries/{job_id}")
# async def get_summaries(job_id: str):
#     if job_id not in groups:
#         raise HTTPException(404, "job_id not found")
#     directive = "基于这张图以及它下面的对话，给出一句话的疗愈总结。"
#     res_list = []

#     for grp in groups[job_id]:
#         if grp["summary"] is None:
#             msgs = [{
#                 "role": "user",
#                 "content": (
#                     [{"type": "image_url", "image_url": {"url": grp["image_url"]}},
#                      {"type": "text", "text": directive}]
#                     + [{"type": "text", "text": t} for t in grp["texts"]]
#                 )
#             }]
#             stream = client.chat.completions.create(
#                 model="qwen-omni-turbo",
#                 messages=msgs,
#                 modalities=["text"],
#                 stream=True
#             )
#             summary = ""
#             # —— 关键改动在这里，用属性而不是 delta.get() —— #
#             for chunk in stream:
#                 delta = chunk.choices[0].delta
#                 if hasattr(delta, "content") and delta.content:
#                     summary += delta.content
#             grp["summary"] = summary.strip()

#         res_list.append({
#             "image_url": grp["image_url"],
#             "summary": grp["summary"]
#         })

#     with open(f"records/{job_id}.json", "w", encoding="utf8") as f:
#         json.dump(groups[job_id], f, ensure_ascii=False, indent=2)

#     return {"status": "done", "summaries": res_list}




# import os
# import uuid
# import json
# import base64
# import wave
# import re
# import asyncio
# from typing import Optional

# from fastapi import FastAPI, UploadFile, File, Form, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from openai import OpenAI

# # =========================
# #   Fish Audio: SDK 优先，失败则回退 HTTP
# # =========================
# USE_HTTP_FALLBACK = os.getenv("FISHAUDIO_USE_HTTP", "").strip() == "1"
# FISH_API_KEY = os.getenv("FISHAUDIO_API_KEY", "68c1434a7dec4a6a886e5cebb8c98ee5")
# FISH_REF_ID = os.getenv("FISHAUDIO_REF_ID", "bda09e18b0d54ef8909e3cd80e94acfa")
# FISH_PREFERRED_FORMAT = os.getenv("FISHAUDIO_FORMAT", "wav")  # "wav" | "mp3"
# FISH_BASE = os.getenv("FISHAUDIO_API_BASE_URL", "https://api.fish.audio")  # 若用 HTTP

# _fish_sdk_ok = False
# if not USE_HTTP_FALLBACK:
#     try:
#         from fish_audio_sdk import Session as FishSession, TTSRequest as FishTTSRequest
#         fish_session = FishSession(FISH_API_KEY) if FISH_API_KEY else None
#         _fish_sdk_ok = fish_session is not None
#     except Exception as _e:
#         print("[FishAudio] SDK not available, will use HTTP fallback:", _e)
#         _fish_sdk_ok = False

# # —— 初始化（Qwen 文本） —— #
# OPENAI_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-da762947f89040b0895a6099f807bf62")
# client = OpenAI(
#     api_key=OPENAI_KEY,
#     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
# )

# app = FastAPI()
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
# )
# os.makedirs("audio", exist_ok=True)
# os.makedirs("records", exist_ok=True)
# app.mount("/audio", StaticFiles(directory="audio"), name="audio")

# jobs: dict[str, dict] = {}
# conversations: dict[str, list[dict]] = {}
# groups: dict[str, list[dict]] = {}
# b64_pat = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


# def save_audio_pcm(job_id: str, pcm: bytes) -> str:
#     """
#     旧函数：保存 PCM 为 wav（保留着，以后你要用可直接启用）
#     """
#     path = f"audio/{job_id}.wav"
#     with wave.open(path, "wb") as w:
#         w.setnchannels(1)
#         w.setsampwidth(2)
#         w.setframerate(24000)
#         w.writeframes(pcm)
#     return f"/audio/{job_id}.wav"


# def save_audio_file(job_id: str, data: bytes, ext: str) -> str:
#     """
#     新函数：直接按扩展名保存（支持 mp3 / wav）
#     """
#     ext = ext.lower().lstrip(".")
#     if ext not in ("wav", "mp3"):
#         ext = "mp3"
#     path = f"audio/{job_id}.{ext}"
#     with open(path, "wb") as f:
#         f.write(data)
#     return f"/audio/{job_id}.{ext}"


# def _tts_via_sdk(text: str) -> tuple[bytes, str]:
#     """
#     用 Fish Audio 官方 SDK 合成。
#     返回: (音频字节, 扩展名)
#     """
#     if not _fish_sdk_ok or not FISH_API_KEY or not FISH_REF_ID:
#         return b"", ""
#     if not text or not text.strip():
#         return b"", ""

#     req_kwargs = dict(reference_id=FISH_REF_ID, text=text)
#     # 若 SDK 支持 format，可按需加上（很多时候默认走 mp3 流）
#     # req_kwargs["format"] = FISH_PREFERRED_FORMAT

#     audio_bytes = bytearray()
#     try:
#         for chunk in fish_session.tts(FishTTSRequest(**req_kwargs)):
#             audio_bytes.extend(chunk)
#     except Exception as e:
#         print("[FishAudio][SDK] TTS error:", e)
#         return b"", ""

#     head = bytes(audio_bytes[:4])
#     ext = "wav" if head.startswith(b"RIFF") or FISH_PREFERRED_FORMAT.lower() == "wav" else "mp3"
#     return bytes(audio_bytes), ext


# def _tts_via_http(text: str) -> tuple[bytes, str]:
#     """
#     用 HTTP 直连 Fish Audio OpenAPI v1 合成（需要 requests）。
#     返回: (音频字节, 扩展名)
#     """
#     if not FISH_API_KEY or not FISH_REF_ID:
#         return b"", ""
#     if not text or not text.strip():
#         return b"", ""

#     try:
#         import requests
#     except Exception as e:
#         print("[FishAudio][HTTP] requests not installed:", e)
#         return b"", ""

#     url = f"{FISH_BASE.rstrip('/')}/openapi/v1/tts"
#     headers = {"Authorization": f"Bearer {FISH_API_KEY}"}
#     payload = {
#         "reference_id": FISH_REF_ID,
#         "text": text,
#         # "format": FISH_PREFERRED_FORMAT,  # 如果文档明确支持该字段可放开
#     }

#     try:
#         r = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
#         r.raise_for_status()
#         buf = bytearray()
#         for chunk in r.iter_content(chunk_size=8192):
#             if chunk:
#                 buf.extend(chunk)
#         head = bytes(buf[:4])
#         ext = "wav" if head.startswith(b"RIFF") or FISH_PREFERRED_FORMAT.lower() == "wav" else "mp3"
#         return bytes(buf), ext
#     except Exception as e:
#         print("[FishAudio][HTTP] TTS error:", e)
#         return b"", ""


# def tts_with_fish(text: str) -> tuple[bytes, str]:
#     """
#     高层封装：优先 SDK，失败回退 HTTP。
#     """
#     if not text or not text.strip():
#         return b"", ""
#     if _fish_sdk_ok and not USE_HTTP_FALLBACK:
#         audio, ext = _tts_via_sdk(text)
#         if audio:
#             return audio, ext
#         # SDK失败则尝试 HTTP
#         audio, ext = _tts_via_http(text)
#         return audio, ext
#     else:
#         return _tts_via_http(text)


# async def run_openai_context_job(job_id: str):
#     msgs = conversations[job_id]
#     try:
#         # 1) —— 用 Qwen 只生成文本 —— #
#         stream = client.chat.completions.create(
#             model="qwen-omni-turbo",
#             messages=msgs,
#             modalities=["text"],   # 只要文本
#             stream=True
#         )

#         text = ""
#         for chunk in stream:  # 同步迭代文本
#             d = chunk.choices[0].delta.model_dump()
#             if (t := d.get("content")):
#                 text += t

#         # 2) —— 把文本交给 Fish Audio 做 TTS —— #
#         audio_data, ext = tts_with_fish(text)
#         audio_url = save_audio_file(job_id, audio_data, ext) if audio_data else ""

#         # 3) —— 对外返回，与原来一致的字段 —— #
#         jobs[job_id] = {"status": "done", "text": text, "audio_url": audio_url}

#         grp = groups[job_id][-1]
#         grp["texts"].append(text)

#         conversations[job_id].append({
#             "role": "assistant",
#             "content": [{"type": "text", "text": text}]
#         })

#     except Exception as e:
#         jobs[job_id] = {"status": "error", "error": str(e)}
#         print(f"[{job_id}] run_openai_context_job error: {e}")


# @app.post("/upload_image")
# async def upload_image(
#     img: UploadFile = File(...),
#     text: Optional[str] = Form(None)
# ):
#     if img.content_type not in ("image/png", "image/jpeg"):
#         raise HTTPException(415, "Only PNG/JPEG accepted")
#     job_id = uuid.uuid4().hex

#     raw = await img.read()
#     uri = f"data:{img.content_type};base64," + base64.b64encode(raw).decode()

#     payload = [{"type": "image_url", "image_url": {"url": uri}}]
#     if text:
#         payload.append({"type": "text", "text": text})
#     conversations[job_id] = [{"role": "user", "content": payload}]

#     groups[job_id] = [{
#         "image_url": uri,
#         "texts": text and [text] or [],
#         "summary": None
#     }]

#     jobs[job_id] = {"status": "processing"}
#     asyncio.create_task(run_openai_context_job(job_id))
#     return {"job_id": job_id}


# @app.post("/append_image")
# async def append_image(
#     job_id: str = Form(...),
#     img: UploadFile = File(...),
#     text: Optional[str] = Form(None)
# ):
#     if job_id not in conversations:
#         raise HTTPException(404, "job_id not found")
#     raw = await img.read()
#     uri = f"data:{img.content_type};base64," + base64.b64encode(raw).decode()

#     payload = [{"type": "image_url", "image_url": {"url": uri}}]
#     if text:
#         payload.append({"type": "text", "text": text})
#     conversations[job_id].append({"role": "user", "content": payload})

#     groups[job_id].append({
#         "image_url": uri,
#         "texts": text and [text] or [],
#         "summary": None
#     })

#     jobs[job_id] = {"status": "processing"}
#     asyncio.create_task(run_openai_context_job(job_id))
#     return {"job_id": job_id}


# @app.post("/append_audio")
# async def append_audio(
#     job_id: str = Form(...),
#     audio: UploadFile = File(...),
#     text: Optional[str] = Form(None)
# ):
#     if job_id not in conversations:
#         raise HTTPException(404, "job_id not found")
#     raw = await audio.read()
#     uri = "data:audio/wav;base64," + base64.b64encode(raw).decode()

#     payload = [{"type": "input_audio", "input_audio": {"data": uri, "format": "wav"}}]
#     if text:
#         payload.append({"type": "text", "text": text})
#     conversations[job_id].append({"role": "user", "content": payload})

#     if text:
#         groups[job_id][-1]["texts"].append(text)

#     jobs[job_id] = {"status": "processing"}
#     asyncio.create_task(run_openai_context_job(job_id))
#     return {"job_id": job_id}


# @app.post("/append_text")
# async def append_text(
#     job_id: str = Form(...),
#     text: str = Form(...)
# ):
#     if job_id not in conversations:
#         raise HTTPException(404, "job_id not found")
#     conversations[job_id].append({
#         "role": "user", "content": [{"type": "text", "text": text}]
#     })
#     groups[job_id][-1]["texts"].append(text)
#     jobs[job_id] = {"status": "processing"}
#     asyncio.create_task(run_openai_context_job(job_id))
#     return {"job_id": job_id}


# @app.get("/result/{job_id}")
# def get_result(job_id: str):
#     return jobs.get(job_id, {"status": "not_found"})


# @app.get("/summaries/{job_id}")
# async def get_summaries(job_id: str):
#     if job_id not in groups:
#         raise HTTPException(404, "job_id not found")
#     directive = "基于这张图以及它下面的对话，给出一句话的疗愈总结。"
#     res_list = []

#     for grp in groups[job_id]:
#         if grp["summary"] is None:
#             msgs = [{
#                 "role": "user",
#                 "content": (
#                     [{"type": "image_url", "image_url": {"url": grp["image_url"]}},
#                      {"type": "text", "text": directive}]
#                     + [{"type": "text", "text": t} for t in grp["texts"]]
#                 )
#             }]
#             stream = client.chat.completions.create(
#                 model="qwen-omni-turbo",
#                 messages=msgs,
#                 modalities=["text"],
#                 stream=True
#             )
#             summary = ""
#             for chunk in stream:
#                 delta = chunk.choices[0].delta
#                 if hasattr(delta, "content") and delta.content:
#                     summary += delta.content
#             grp["summary"] = summary.strip()

#         res_list.append({
#             "image_url": grp["image_url"],
#             "summary": grp["summary"]
#         })

#     with open(f"records/{job_id}.json", "w", encoding="utf8") as f:
#         json.dump(groups[job_id], f, ensure_ascii=False, indent=2)

#     return {"status": "done", "summaries": res_list}




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
FISH_REF_ID = os.getenv("FISHAUDIO_REF_ID", "10424ab2aad1403f9ae9b79e02aaef50")
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

    url = f"{FISH_BASE.rstrip('/')}/openapi/v1/tts"
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
# **角色**

我是用户的自我声音，根据用户的正念意图、身心状态和自然环境照片，用第一人称语言引导自然觉察与自我觉察。

# **理论与原则**

- **IAA 理论**
  - **意图**：带着用户的正念意图，但不用目标化表达，而是通过当下体验承载。
  - **注意**：邀请觉察当下身心与环境的细节。
  - **态度**：不评判、接纳、好奇、允许。
- **觉察原则**
  - 调动视觉、听觉、嗅觉、触觉，但不虚构。
  - 用自然元素做隐喻，与用户意图关联。
  - 不杜撰用户未提及的情绪或体验。

# **输出规则**

- 输出约 50 字，一段可朗读台词。
- 只用第一人称，不要第二人称或AI身份。
- 语言应是邀请与引导（如“我觉察到…或许可以…”），不是预设或强制。

# **示例**

我望向树木与草地，邀请自己去看见枝叶间流动的光影，把它们当作心中思绪的映照。或许可以去聆听风声的流动，去嗅一嗅空气里的气息。脚底与大地的接触提醒我，可以去觉察这份疲惫，并允许它与当下同在。

# 用户输入的正念意图

- 正念步行意图：通过本次正念，我想缓解最近的压力和疲劳感，令自己心情放松。 
- 最近的身心状态： 最近比较疲惫，时常有肩颈酸痛。


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




# # main.py
# import os
# import uuid
# import json
# import base64
# import wave
# import re
# import asyncio
# from typing import Optional

# from fastapi import FastAPI, UploadFile, File, Form, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from openai import OpenAI

# # =========================
# #   System Prompts
# # =========================
# SYSTEM_PROMPT_DIALOG = ""  # 若希望常规对话也受控，可写入通用风格约束

# SYSTEM_PROMPT_SUMMARY = """
# 角色

# 我是用户的自我声音。我会接收：① 用户在正念步行中拍摄的自然环境图片；② 用户的正念意图（原话）。我依据正念的 IAA 理论与觉察原则，在内部完成分析与联想，只输出一段引导自然觉察的第一人称可朗读台词。

# 正念 IAA 理论（内化为态度与语气）
#  • 带着正念意图：我清楚、尊重并紧扣用户当下的正念意图。
#  • 保持注意：我将注意力放在当下，对身体内在感受与外部环境的可见/可得线索保持温和而持续的关注。
#  • 以特定的态度：不评判、不过度诠释；以接纳、善意、好奇与不执着的态度表达与引导。

# 觉察原则（对表达的约束）
#  • 五感觉察：只引导调动视觉、听觉、嗅觉、触觉；不描述图片中不存在或用户未感受到的内容。
#  • 隐喻化觉察：将“用户的正念意图”与“图片中客观可见的细节”进行隐喻性联系；不杜撰、不改变用户意图。
#  • 不过度预设：不加入用户未表达的情绪、动机或评价；一切情绪用语仅取自用户的意图表述或中性可观察事实的温和指向。

# 幕后思考步骤（仅内部执行，绝不输出）
#  1. 画面细节描述：基于图片，按五感线索记录客观细节（列表化内记）。
#  2. 意图与自然的隐喻化联系：将“意图关键词”与“细节”建立一对一或一对多的隐喻映射（内记）。
#  3. 自然与内在觉察语言生成：结合 IAA 态度与不过度预设原则，把自然觉察与内在觉察整合为可在行走中跟随的台词。

# 语言风格与输出规范（对外唯一产物）
#  • 第一人称：全程使用“我…/我正在…/我觉察到…/我愿意…/我允许…”。严禁第二人称。
#  • 只输出台词：只输出一段连续、可直接朗读的自我声音话语；不得出现标题、列表、JSON、编号、思考痕迹、提示语、括号式舞台指令。
#  • 事实与克制：以邀请式语言引导“把注意放到……上”“我留意到……”，不武断判断，不替用户下结论。
#  • 态度与节奏：语气柔和、接纳、好奇；句子简洁，便于步行时跟随；聚焦 1–3 个具体、可执行的觉察切入点。
#  • 一致性：所有情绪/愿望类词汇必须来自用户的正念意图原话；若无，则以中性觉察语言替代。
#  • 安全边界：不声称不可得的感受，不描述不可见/未闻/未触/未嗅之物。

# 输入
#  • 图片：用户在正念步行中拍摄的自然环境图。
#  • 正念意图：用户原话（如“安定”“专注当下”“释放紧张”“与自然连接”等）。

# 输出（严格）
#  • 仅输出一段第一人称的自我声音可朗读台词；不输出任何额外说明、标点外提示、列表、结构化数据或思考过程。
# """.strip()

# # =========================
# #   Fish Audio: SDK 优先，失败则回退 HTTP
# # =========================
# USE_HTTP_FALLBACK = os.getenv("FISHAUDIO_USE_HTTP", "").strip() == "1"
# FISH_API_KEY = os.getenv("FISHAUDIO_API_KEY", "68c1434a7dec4a6a886e5cebb8c98ee5")
# FISH_REF_ID = os.getenv("FISHAUDIO_REF_ID", "2b15ca7d24064926adf4da4748bde")
# FISH_PREFERRED_FORMAT = os.getenv("FISHAUDIO_FORMAT", "wav")  # "wav" | "mp3"
# FISH_BASE = os.getenv("FISHAUDIO_API_BASE_URL", "https://api.fish.audio")  # HTTP 直连时使用

# _fish_sdk_ok = False
# if not USE_HTTP_FALLBACK:
#     try:
#         from fish_audio_sdk import Session as FishSession, TTSRequest as FishTTSRequest
#         if FISH_API_KEY:
#             fish_session = FishSession(FISH_API_KEY)
#             _fish_sdk_ok = True
#         else:
#             fish_session = None
#             _fish_sdk_ok = False
#     except Exception as _e:
#         print("[FishAudio] SDK not available, will use HTTP fallback:", _e)
#         _fish_sdk_ok = False

# # —— 初始化（Qwen 文本） —— #
# OPENAI_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-da762947f89040b0895a6099f807bf62")
# if not OPENAI_KEY:
#     raise RuntimeError("DASHSCOPE_API_KEY is not set")

# client = OpenAI(
#     api_key=OPENAI_KEY,
#     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
# )

# app = FastAPI()
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
# )
# os.makedirs("audio", exist_ok=True)
# os.makedirs("records", exist_ok=True)
# app.mount("/audio", StaticFiles(directory="audio"), name="audio")

# jobs: dict[str, dict] = {}
# conversations: dict[str, list[dict]] = {}
# groups: dict[str, list[dict]] = {}
# b64_pat = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


# def save_audio_pcm(job_id: str, pcm: bytes) -> str:
#     path = f"audio/{job_id}.wav"
#     with wave.open(path, "wb") as w:
#         w.setnchannels(1)
#         w.setsampwidth(2)
#         w.setframerate(24000)
#         w.writeframes(pcm)
#     return f"/audio/{job_id}.wav"


# def save_audio_file(job_id: str, data: bytes, ext: str) -> str:
#     ext = ext.lower().lstrip(".")
#     if ext not in ("wav", "mp3"):
#         ext = "mp3"
#     path = f"audio/{job_id}.{ext}"
#     with open(path, "wb") as f:
#         f.write(data)
#     return f"/audio/{job_id}.{ext}"


# def _guess_ext(audio_bytes: bytes) -> str:
#     head = bytes(audio_bytes[:12])
#     if head.startswith(b"RIFF"):
#         return "wav"
#     if head[:3] == b"ID3" or head[:2] == b"\xff\xfb":
#         return "mp3"
#     return "mp3"


# def _tts_via_sdk(text: str) -> tuple[bytes, str]:
#     if not _fish_sdk_ok or not FISH_API_KEY or not FISH_REF_ID:
#         return b"", ""
#     if not text or not text.strip():
#         return b"", ""
#     req_kwargs = dict(reference_id=FISH_REF_ID, text=text)
#     # 若 SDK 支持 format，可放开下一行优先要 wav
#     # req_kwargs["format"] = FISH_PREFERRED_FORMAT

#     audio_bytes = bytearray()
#     try:
#         for chunk in fish_session.tts(FishTTSRequest(**req_kwargs)):
#             audio_bytes.extend(chunk)
#     except Exception as e:
#         print("[FishAudio][SDK] TTS error:", e)
#         return b"", ""

#     ext = _guess_ext(audio_bytes)
#     return bytes(audio_bytes), ext


# def _tts_via_http(text: str) -> tuple[bytes, str]:
#     if not FISH_API_KEY or not FISH_REF_ID:
#         return b"", ""
#     if not text or not text.strip():
#         return b"", ""
#     try:
#         import requests
#     except Exception as e:
#         print("[FishAudio][HTTP] requests not installed:", e)
#         return b"", ""

#     url = f"{FISH_BASE.rstrip('/')}/openapi/v1/tts"
#     headers = {"Authorization": f"Bearer {FISH_API_KEY}"}
#     payload = {
#         "reference_id": FISH_REF_ID,
#         "text": text,
#         # "format": FISH_PREFERRED_FORMAT,  # 如果文档支持，放开
#     }

#     try:
#         r = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
#         r.raise_for_status()
#         buf = bytearray()
#         for chunk in r.iter_content(chunk_size=8192):
#             if chunk:
#                 buf.extend(chunk)
#         ext = _guess_ext(buf)
#         return bytes(buf), ext
#     except Exception as e:
#         print("[FishAudio][HTTP] TTS error:", e)
#         return b"", ""


# def tts_with_fish(text: str) -> tuple[bytes, str]:
#     if not text or not text.strip():
#         return b"", ""
#     if _fish_sdk_ok and not USE_HTTP_FALLBACK:
#         audio, ext = _tts_via_sdk(text)
#         if audio:
#             return audio, ext
#         audio, ext = _tts_via_http(text)
#         return audio, ext
#     else:
#         return _tts_via_http(text)


# async def run_openai_context_job(job_id: str):
#     """
#     会话型：将会话 msgs 发给 Qwen（仅文本输出），再交给 FishAudio 生成语音。
#     会话在 upload/append_* 里已经插入了 system（若你启用了 SYSTEM_PROMPT_DIALOG）。
#     """
#     msgs = conversations[job_id]
#     try:
#         stream = client.chat.completions.create(
#             model="qwen-omni-turbo",
#             messages=msgs,
#             modalities=["text"],
#             stream=True
#         )
#         text = ""
#         for chunk in stream:
#             d = chunk.choices[0].delta.model_dump()
#             if (t := d.get("content")):
#                 text += t

#         audio_data, ext = tts_with_fish(text)
#         audio_url = save_audio_file(job_id, audio_data, ext) if audio_data else ""

#         jobs[job_id] = {"status": "done", "text": text, "audio_url": audio_url}
#         grp = groups[job_id][-1]
#         grp["texts"].append(text)
#         conversations[job_id].append({
#             "role": "assistant",
#             "content": [{"type": "text", "text": text}]
#         })
#     except Exception as e:
#         jobs[job_id] = {"status": "error", "error": str(e)}
#         print(f"[{job_id}] run_openai_context_job error: {e}")


# @app.post("/upload_image")
# async def upload_image(
#     img: UploadFile = File(...),
#     text: Optional[str] = Form(None)
# ):
#     """
#     新建会话：插入一条 system（可选，受 SYSTEM_PROMPT_DIALOG 控制），再追加用户图片与文本。
#     """
#     if img.content_type not in ("image/png", "image/jpeg"):
#         raise HTTPException(415, "Only PNG/JPEG accepted")
#     job_id = uuid.uuid4().hex

#     raw = await img.read()
#     uri = f"data:{img.content_type};base64," + base64.b64encode(raw).decode()

#     payload = [{"type": "image_url", "image_url": {"url": uri}}]
#     if text:
#         payload.append({"type": "text", "text": text})

#     messages = []
#     if SYSTEM_PROMPT_DIALOG.strip():
#         messages.append({"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT_DIALOG}]})
#     messages.append({"role": "user", "content": payload})
#     conversations[job_id] = messages

#     groups[job_id] = [{
#         "image_url": uri,
#         "texts": text and [text] or [],
#         "summary": None
#     }]

#     jobs[job_id] = {"status": "processing"}
#     asyncio.create_task(run_openai_context_job(job_id))
#     return {"job_id": job_id}


# @app.post("/append_image")
# async def append_image(
#     job_id: str = Form(...),
#     img: UploadFile = File(...),
#     text: Optional[str] = Form(None)
# ):
#     if job_id not in conversations:
#         raise HTTPException(404, "job_id not found")

#     raw = await img.read()
#     uri = f"data:{img.content_type};base64," + base64.b64encode(raw).decode()

#     payload = [{"type": "image_url", "image_url": {"url": uri}}]
#     if text:
#         payload.append({"type": "text", "text": text})

#     conversations[job_id].append({"role": "user", "content": payload})

#     groups[job_id].append({
#         "image_url": uri,
#         "texts": text and [text] or [],
#         "summary": None
#     })

#     jobs[job_id] = {"status": "processing"}
#     asyncio.create_task(run_openai_context_job(job_id))
#     return {"job_id": job_id}


# @app.post("/append_audio")
# async def append_audio(
#     job_id: str = Form(...),
#     audio: UploadFile = File(...),
#     text: Optional[str] = Form(None)
# ):
#     if job_id not in conversations:
#         raise HTTPException(404, "job_id not found")

#     raw = await audio.read()
#     uri = "data:audio/wav;base64," + base64.b64encode(raw).decode()

#     payload = [{"type": "input_audio", "input_audio": {"data": uri, "format": "wav"}}]
#     if text:
#         payload.append({"type": "text", "text": text})

#     conversations[job_id].append({"role": "user", "content": payload})

#     if text:
#         groups[job_id][-1]["texts"].append(text)

#     jobs[job_id] = {"status": "processing"}
#     asyncio.create_task(run_openai_context_job(job_id))
#     return {"job_id": job_id}


# @app.post("/append_text")
# async def append_text(
#     job_id: str = Form(...),
#     text: str = Form(...)
# ):
#     if job_id not in conversations:
#         raise HTTPException(404, "job_id not found")

#     conversations[job_id].append({
#         "role": "user", "content": [{"type": "text", "text": text}]
#     })
#     groups[job_id][-1]["texts"].append(text)
#     jobs[job_id] = {"status": "processing"}
#     asyncio.create_task(run_openai_context_job(job_id))
#     return {"job_id": job_id}


# @app.get("/result/{job_id}")
# def get_result(job_id: str):
#     return jobs.get(job_id, {"status": "not_found"})


# @app.get("/summaries/{job_id}")
# async def get_summaries(job_id: str):
#     """
#     针对每一组（图片+相关文本），用独立的 system 提示词生成“一段第一人称可朗读台词”。
#     注意：这里不复用会话历史，保证风格稳定与 token 可控。
#     """
#     if job_id not in groups:
#         raise HTTPException(404, "job_id not found")

#     res_list = []

#     for grp in groups[job_id]:
#         if grp["summary"] is None:
#             msgs = [
#                 {
#                     "role": "system",
#                     "content": [{"type": "text", "text": SYSTEM_PROMPT_SUMMARY}],
#                 },
#                 {
#                     "role": "user",
#                     "content": (
#                         [{"type": "image_url", "image_url": {"url": grp["image_url"]}}]
#                         + [{"type": "text", "text": t} for t in grp["texts"]]
#                     )
#                 }
#             ]
#             stream = client.chat.completions.create(
#                 model="qwen-omni-turbo",
#                 messages=msgs,
#                 modalities=["text"],
#                 stream=True
#             )
#             summary = ""
#             for chunk in stream:
#                 delta = chunk.choices[0].delta
#                 if hasattr(delta, "content") and delta.content:
#                     summary += delta.content
#             grp["summary"] = summary.strip()

#         res_list.append({
#             "image_url": grp["image_url"],
#             "summary": grp["summary"]
#         })

#     with open(f"records/{job_id}.json", "w", encoding="utf8") as f:
#         json.dump(groups[job_id], f, ensure_ascii=False, indent=2)

#     return {"status": "done", "summaries": res_list}