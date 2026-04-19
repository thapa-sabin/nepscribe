#!/usr/bin/env python3
"""
ASR + SOAP summarization pipeline.
- Transcribes audio with faster-whisper (CPU, macOS-friendly).
- Produces a transcript text file.
- Summarizes into SOAP notes using a Hugging Face chat model via LangChain.

Usage:
  python asr_pipeline.py \
    --audio /path/to/audio.mp3 \
    --out-dir /path/to/output \
    --hf-model meta-llama/Llama-3.1-8B-Instruct

Environment:
  export HUGGINGFACEHUB_API_TOKEN="your_token_here"

Dependencies:
  pip install pydub faster-whisper langchain-huggingface langchain-core
"""

import argparse
import gc
import os
from pathlib import Path

from dotenv import load_dotenv

from pydub import AudioSegment
from faster_whisper import WhisperModel
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Load environment variables from .env (if present)
load_dotenv()


def cleanup_all():
    """Run GC to keep memory usage steady on small machines."""
    gc.collect()


def preprocess_audio(audio_path: Path, out_dir: Path) -> Path:
    """
    Convert audio to mono 16kHz WAV for ASR.
    Returns the path to the processed WAV file.
    """
    audio = AudioSegment.from_file(audio_path)
    audio = audio.set_channels(1).set_frame_rate(16000)

    processed_path = out_dir / f"{audio_path.stem}_mono16k.wav"
    audio.export(processed_path, format="wav")
    return processed_path


def transcribe_audio(wav_path: Path, out_dir: Path, model_size: str = "small") -> Path:
    """
    Transcribe the WAV file using faster-whisper (CPU).
    Returns the transcript text file path.
    """
    asr_model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = asr_model.transcribe(str(wav_path), beam_size=5)

    transcript_text = " ".join(seg.text.strip() for seg in segments)

    transcript_path = out_dir / "full_transcript.txt"
    transcript_path.write_text(transcript_text.strip(), encoding="utf-8")

    # Free memory
    del asr_model
    cleanup_all()

    return transcript_path


def summarize_soap(transcript_text: str, repo_id: str, max_new_tokens: int = 1024) -> str:
    """
    Generate SOAP notes using a Hugging Face chat model.
    """
    token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if not token:
        raise RuntimeError("HUGGINGFACEHUB_API_TOKEN is not set.")

    llm = HuggingFaceEndpoint(
        repo_id=repo_id,
        task="text-generation",
        max_new_tokens=max_new_tokens,
        temperature=0.01,
    )

    chat_model = ChatHuggingFace(llm=llm)

    soap_template = [
        (
            "system",
            "You are a medical scribe. Convert the transcript into a formal SOAP note. "
            "If a section has no information, write 'Not mentioned'. Output exactly:\n"
            "S: ...\nO: ...\nA: ...\nP: ...",
        ),
        ("human", "Transcript:\n{transcript}"),
    ]

    prompt = ChatPromptTemplate.from_messages(soap_template)
    chain = prompt | chat_model | StrOutputParser()

    return chain.invoke({"transcript": transcript_text})


def main():
    parser = argparse.ArgumentParser(description="ASR + SOAP summarization pipeline")
    parser.add_argument("--audio", required=True, help="Path to input audio file (.mp3/.wav)")
    parser.add_argument("--out-dir", default="output", help="Output directory")
    parser.add_argument("--hf-model", default="meta-llama/Llama-3.1-8B-Instruct", help="HF repo id")
    parser.add_argument("--asr-model", default="small", help="Whisper model size: tiny/base/small")
    args = parser.parse_args()

    audio_path = Path(args.audio).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    processed_wav = preprocess_audio(audio_path, out_dir)
    transcript_path = transcribe_audio(processed_wav, out_dir, model_size=args.asr_model)

    transcript_text = transcript_path.read_text(encoding="utf-8")
    soap_notes = summarize_soap(transcript_text, repo_id=args.hf_model)

    soap_path = out_dir / "soap_notes.txt"
    soap_path.write_text(soap_notes, encoding="utf-8")

    print(f"Transcript saved: {transcript_path}")
    print(f"SOAP notes saved: {soap_path}")


if __name__ == "__main__":
    main()
