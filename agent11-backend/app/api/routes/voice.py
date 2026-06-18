"""语音 API - 语音识别（STT）+ 语音合成（TTS）"""
import os, tempfile, structlog
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

logger = structlog.get_logger()
router = APIRouter()

# Whisper 模型（延迟加载）
_model = None


def get_model():
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
            # 使用本地模型路径（避免从 Hugging Face 下载）
            import os
            model_path = os.environ.get("WHISPER_MODEL_PATH", "/home/ubuntu/whisper_model")
            if not os.path.exists(model_path):
                model_path = "small"  # 兜底：在线下载
            logger.info("loading_whisper_model", path=model_path)
            _model = WhisperModel(model_path, device="cpu", compute_type="int8")
            logger.info("whisper_model_loaded", path=model_path)
        except Exception as e:
            logger.error("whisper_load_failed", error=str(e))
            raise
    return _model


class TTSRequest(BaseModel):
    text: str
    language: str = "zh-HK"  # zh-HK | en-US


@router.post("/voice/stt")
async def speech_to_text(file: UploadFile = File(...)):
    """语音识别：接收音频文件，返回识别文本"""
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(400, "Only audio files supported")

    # Save uploaded audio to temp file
    suffix = ".wav"
    if file.filename:
        ext = os.path.splitext(file.filename)[1]
        if ext:
            suffix = ext

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        import subprocess
        resampled_path = tmp_path + "_16k.wav"
        logger.info("stt_ffmpeg_start", input_size=os.path.getsize(tmp_path))
        result = subprocess.run([
            "ffmpeg", "-y", "-i", tmp_path,
            "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
            resampled_path
        ], capture_output=True, timeout=30)
        if result.returncode != 0:
            logger.error("stt_ffmpeg_failed", stderr=result.stderr[:300])
            raise RuntimeError(f"ffmpeg error: {result.stderr[:200]}")
        wav_size = os.path.getsize(resampled_path)
        logger.info("stt_ffmpeg_done", resampled_size=wav_size)

        # Check if the resampled file has actual audio data (WAV > 44 bytes header)
        if wav_size < 1000:
            logger.warning("stt_ffmpeg_too_small", size=wav_size)

        model = get_model()
        segments, info = model.transcribe(resampled_path, beam_size=3, vad_filter=True)

        detected_lang = info.language
        text_parts = []
        for seg in segments:
            text_parts.append(seg.text.strip())

        full_text = " ".join(text_parts)
        logger.info("stt_result", language=detected_lang, text=full_text[:100])

        try:
            os.unlink(resampled_path)
        except Exception:
            pass

        return {
            "text": full_text,
            "language": detected_lang,
            "segments": len(text_parts),
        }
    except Exception as e:
        logger.error("stt_failed", error=str(e))
        raise HTTPException(500, f"STT failed: {str(e)}")
    finally:
        os.unlink(tmp_path)


@router.post("/voice/detect")
async def detect_language(file: UploadFile = File(...)):
    """仅检测音频语言（不转写）"""
    import tempfile
    suffix = ".wav"
    if file.filename:
        ext = os.path.splitext(file.filename)[1]
        if ext:
            suffix = ext

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        model = get_model()
        segments, info = model.transcribe(tmp_path, beam_size=1, vad_filter=True)
        return {"language": info.language, "probability": info.language_probability}
    except Exception as e:
        raise HTTPException(500, f"Detection failed: {str(e)}")
    finally:
        os.unlink(tmp_path)
