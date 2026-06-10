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
            model_size = os.environ.get("WHISPER_MODEL", "small")
            logger.info("loading_whisper_model", model=model_size)
            _model = WhisperModel(model_size, device="cpu", compute_type="int8")
            logger.info("whisper_model_loaded", model=model_size)
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
        model = get_model()
        segments, info = model.transcribe(tmp_path, beam_size=3, vad_filter=True)

        detected_lang = info.language
        text_parts = []
        for seg in segments:
            text_parts.append(seg.text.strip())

        full_text = " ".join(text_parts)
        logger.info("stt_result", language=detected_lang, text=full_text[:100])

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
