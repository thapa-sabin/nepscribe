#!/usr/bin/env python3
"""
FastAPI service for Rails monolith integration.

What it provides:
- Audio -> transcript + speaker diarization (WhisperX + Pyannote)
- Transcript -> SOAP notes (Llama via HuggingFace LangChain wrapper)
- Full pipeline endpoint
- Async job-style endpoints Rails ActiveJob can submit and poll

Run:
  uvicorn app:app --host 0.0.0.0 --port 8000 --reload

Environment (.env):
  HUGGINGFACEHUB_API_TOKEN=...
  HF_SOAP_MODEL=meta-llama/Llama-3.1-8B-Instruct   (optional)
  WHISPERX_MODEL=small                               (optional)
"""

from __future__ import annotations

import gc
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import torch
import whisperx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from whisperx.diarize import DiarizationPipeline

from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

import warnings

warnings.filterwarnings("ignore", message=".*torchaudio._backend.list_audio_backends.*")

load_dotenv()

app = FastAPI(title="Medical AI Pipeline API", version="1.0.0")


class SoapRequest(BaseModel):
    transcript_text: str = Field(min_length=1)
    repo_id: Optional[str] = None
    max_new_tokens: int = 1024


class SoapSections(BaseModel):
    subjective: str
    objective: str
    assessment: str
    plan: str


class TranscribeResponse(BaseModel):
    transcript_text: str
    diarized_transcript_text: str


class SoapResponse(BaseModel):
    soap_text: str
    soap: SoapSections


class PipelineResponse(BaseModel):
    transcript_text: str
    diarized_transcript_text: str
    soap_text: str
    soap: SoapSections


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    recording_id: Optional[int] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class JobResultResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[PipelineResponse] = None
    error: Optional[str] = None


# In-memory job store for Rails polling.
# Rails remains source-of-truth in SQLite; this only tracks API task state.
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cleanup() -> None:
    gc.collect()


def _get_hf_token() -> str:
    token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if not token:
        raise RuntimeError("HUGGINGFACEHUB_API_TOKEN is not set")
    return token


def _build_chat_model(
    repo_id: Optional[str], max_new_tokens: int = 1024
) -> ChatHuggingFace:
    _get_hf_token()
    model_id = repo_id or os.getenv("HF_SOAP_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

    llm = HuggingFaceEndpoint(
        repo_id=model_id,
        task="text-generation",
        max_new_tokens=max_new_tokens,
        temperature=0.01,
    )
    return ChatHuggingFace(llm=llm)


def _extract_soap_sections(text: str) -> SoapSections:
    def pick(label: str) -> str:
        pattern = rf"(?ims)^\s*{label}:\s*(.*?)(?=^\s*[SOAP]:\s*|\Z)"
        m = re.search(pattern, text)
        return m.group(1).strip() if m else "Not mentioned"

    return SoapSections(
        subjective=pick("S"),
        objective=pick("O"),
        assessment=pick("A"),
        plan=pick("P"),
    )


def _generate_soap(
    transcript_text: str, repo_id: Optional[str], max_new_tokens: int = 1024
) -> SoapResponse:
    chat_model = _build_chat_model(repo_id=repo_id, max_new_tokens=max_new_tokens)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a medical scribe. Convert transcript to SOAP notes. "
                "Use only transcript content. If missing, write 'Not mentioned'. "
                "Output exactly:\nS: ...\nO: ...\nA: ...\nP: ...",
            ),
            ("human", "Transcript:\n{transcript}"),
        ]
    )

    chain = prompt | chat_model | StrOutputParser()
    soap_text = chain.invoke({"transcript": transcript_text})
    sections = _extract_soap_sections(soap_text)
    return SoapResponse(soap_text=soap_text, soap=sections)


def _transcribe_and_diarize(
    audio_path: Path, model_size: Optional[str] = None
) -> TranscribeResponse:
    _get_hf_token()

    model_name = model_size or os.getenv("WHISPERX_MODEL", "small")
    device = "cpu"
    compute_type = "int8"

    # PyTorch 2.6+ checkpoint safe-loading compatibility for pyannote stack.
    os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
    try:
        from omegaconf.dictconfig import DictConfig
        from omegaconf.listconfig import ListConfig

        torch.serialization.add_safe_globals([ListConfig, DictConfig])
    except Exception:
        pass

    # Use silero VAD to avoid pyannote VAD load issues while keeping true pyannote diarization.
    audio = whisperx.load_audio(str(audio_path))
    asr_model = whisperx.load_model(
        model_name, device, compute_type=compute_type, vad_method="silero"
    )
    result = asr_model.transcribe(audio)

    transcript_text = " ".join(
        seg.get("text", "").strip() for seg in result.get("segments", [])
    ).strip()

    align_model, metadata = whisperx.load_align_model(
        language_code=result["language"], device=device
    )
    aligned = whisperx.align(result["segments"], align_model, metadata, audio, device)

    diarize_model = DiarizationPipeline(use_auth_token=_get_hf_token(), device=device)
    diarize_segments = diarize_model(audio)
    diarized = whisperx.assign_word_speakers(diarize_segments, aligned)

    lines = []
    for seg in diarized.get("segments", []):
        speaker = seg.get("speaker", "SPEAKER_00")
        text = seg.get("text", "").strip()
        if text:
            lines.append(f"{speaker}: {text}")

    diarized_text = "\n".join(lines).strip()

    _cleanup()
    return TranscribeResponse(
        transcript_text=transcript_text,
        diarized_transcript_text=diarized_text,
    )


def _run_full_pipeline(
    audio_path: Path,
    asr_model: Optional[str],
    soap_model: Optional[str],
    max_new_tokens: int,
) -> PipelineResponse:
    tr = _transcribe_and_diarize(audio_path=audio_path, model_size=asr_model)
    soap = _generate_soap(
        transcript_text=tr.transcript_text,
        repo_id=soap_model,
        max_new_tokens=max_new_tokens,
    )
    return PipelineResponse(
        transcript_text=tr.transcript_text,
        diarized_transcript_text=tr.diarized_transcript_text,
        soap_text=soap.soap_text,
        soap=soap.soap,
    )


def _set_job(job_id: str, **kwargs: Any) -> None:
    with JOBS_LOCK:
        if job_id not in JOBS:
            JOBS[job_id] = {}
        JOBS[job_id].update(kwargs)
        JOBS[job_id]["updated_at"] = _utc_now_iso()


def _run_pipeline_job(
    job_id: str,
    audio_bytes: bytes,
    filename: str,
    recording_id: Optional[int],
    asr_model: Optional[str],
    soap_model: Optional[str],
    max_new_tokens: int,
) -> None:
    _set_job(job_id, status="running")

    try:
        with tempfile.TemporaryDirectory(prefix="rails_ai_") as td:
            suffix = Path(filename or "audio.wav").suffix or ".wav"
            audio_path = Path(td) / f"input{suffix}"
            audio_path.write_bytes(audio_bytes)

            result = _run_full_pipeline(
                audio_path=audio_path,
                asr_model=asr_model,
                soap_model=soap_model,
                max_new_tokens=max_new_tokens,
            )

        _set_job(job_id, status="completed", result=result.model_dump())

    except Exception as e:
        _set_job(job_id, status="failed", error=str(e))


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/transcribe", response_model=TranscribeResponse)
async def transcribe_endpoint(
    audio_file: UploadFile = File(...),
    asr_model: Optional[str] = Form(default=None),
) -> TranscribeResponse:
    try:
        with tempfile.TemporaryDirectory(prefix="rails_ai_tr_") as td:
            suffix = Path(audio_file.filename or "audio.wav").suffix or ".wav"
            audio_path = Path(td) / f"input{suffix}"
            audio_path.write_bytes(await audio_file.read())
            return _transcribe_and_diarize(audio_path=audio_path, model_size=asr_model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"transcribe failed: {e}")


@app.post("/v1/soap", response_model=SoapResponse)
def soap_endpoint(req: SoapRequest) -> SoapResponse:
    try:
        return _generate_soap(
            transcript_text=req.transcript_text,
            repo_id=req.repo_id,
            max_new_tokens=req.max_new_tokens,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"soap failed: {e}")


@app.post("/v1/pipeline", response_model=PipelineResponse)
async def pipeline_endpoint(
    audio_file: UploadFile = File(...),
    asr_model: Optional[str] = Form(default=None),
    soap_model: Optional[str] = Form(default=None),
    max_new_tokens: int = Form(default=1024),
) -> PipelineResponse:
    try:
        with tempfile.TemporaryDirectory(prefix="rails_ai_pipe_") as td:
            suffix = Path(audio_file.filename or "audio.wav").suffix or ".wav"
            audio_path = Path(td) / f"input{suffix}"
            audio_path.write_bytes(await audio_file.read())

            return _run_full_pipeline(
                audio_path=audio_path,
                asr_model=asr_model,
                soap_model=soap_model,
                max_new_tokens=max_new_tokens,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pipeline failed: {e}")


@app.post("/v1/jobs/pipeline", response_model=JobStatusResponse)
async def pipeline_job_submit(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    recording_id: Optional[int] = Form(default=None),
    asr_model: Optional[str] = Form(default=None),
    soap_model: Optional[str] = Form(default=None),
    max_new_tokens: int = Form(default=1024),
) -> JobStatusResponse:
    job_id = str(uuid.uuid4())
    now = _utc_now_iso()

    with JOBS_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "recording_id": recording_id,
            "error": None,
            "result": None,
            "created_at": now,
            "updated_at": now,
        }

    audio_bytes = await audio_file.read()
    background_tasks.add_task(
        _run_pipeline_job,
        job_id,
        audio_bytes,
        audio_file.filename or "audio.wav",
        recording_id,
        asr_model,
        soap_model,
        max_new_tokens,
    )

    return JobStatusResponse(**JOBS[job_id])


@app.get("/v1/jobs/{job_id}", response_model=JobStatusResponse)
def pipeline_job_status(job_id: str) -> JobStatusResponse:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        recording_id=job.get("recording_id"),
        error=job.get("error"),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
    )


@app.get("/v1/jobs/{job_id}/result", response_model=JobResultResponse)
def pipeline_job_result(job_id: str) -> JobResultResponse:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    result = job.get("result")
    parsed = PipelineResponse(**result) if result else None
    return JobResultResponse(
        job_id=job["job_id"],
        status=job["status"],
        result=parsed,
        error=job.get("error"),
    )
