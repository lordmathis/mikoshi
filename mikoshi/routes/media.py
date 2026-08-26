import io

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response

router = APIRouter()


@router.post("/media/transcribe")
async def transcribe_audio(request: Request, file: UploadFile = File(...)):
    """
    Transcribe an audio file using the configured ASR service.
    """
    transcription_cfg = request.app.state.app_config.audio.transcription

    # Check if transcription service is configured
    if not transcription_cfg.base_url:
        raise HTTPException(
            status_code=503,
            detail="Transcription service not configured. Please set audio.transcription.base_url in config.yaml",
        )

    # Read the audio file
    try:
        audio_content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to read audio file: {str(e)}"
        )

    # httpx accepts file-like objects directly; no temp file needed.
    files = {
        "file": (file.filename or "audio", io.BytesIO(audio_content), file.content_type)
    }

    data = {
        "model": transcription_cfg.model,
    }
    headers = {}
    if transcription_cfg.api_key:
        headers["Authorization"] = f"Bearer {transcription_cfg.api_key}"

    # Make request to the transcription service
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{transcription_cfg.base_url}/v1/audio/transcriptions",
                files=files,
                data=data,
                headers=headers,
                timeout=300.0,
            )

            # Check response status
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Transcription service error: {response.text}",
                )

            # Return the transcription result
            return response.json()

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504, detail="Transcription service timeout"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to connect to transcription service: {str(e)}",
            )


@router.post("/media/speech")
async def generate_speech(request: Request, body: dict):
    """
    Generate audio from text using the configured TTS service.
    """
    tts_cfg = request.app.state.app_config.audio.tts

    if not tts_cfg.base_url:
        raise HTTPException(
            status_code=503,
            detail="TTS service not configured. Please set audio.tts.base_url in config.yaml",
        )

    input_text = body.get("input", "")
    payload = {"model": tts_cfg.model, "input": input_text, "voice": tts_cfg.voice}
    if tts_cfg.response_format:
        payload["response_format"] = tts_cfg.response_format
    if tts_cfg.speed:
        payload["speed"] = tts_cfg.speed

    headers = {"Content-Type": "application/json"}
    if tts_cfg.api_key:
        headers["Authorization"] = f"Bearer {tts_cfg.api_key}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{tts_cfg.base_url}/v1/audio/speech",
                json=payload,
                headers=headers,
                timeout=60.0,
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"TTS service error: {response.text}",
                )

            return Response(
                content=response.content,
                media_type=f"audio/{tts_cfg.response_format or 'wav'}",
            )

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="TTS service timeout")
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to connect to TTS service: {str(e)}",
            )
