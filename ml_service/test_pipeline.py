from app import _transcribe_and_diarize, _generate_soap
from pathlib import Path
import os

os.environ["HUGGINGFACEHUB_API_TOKEN"] = "<YOUR_TOKEN>"
audio_path = Path("./audio/doc_patient_convo.mp3")

# Transcribe + diarize
transcribe_result = _transcribe_and_diarize(audio_path=audio_path, model_size="small")
print("Transcript:\n", transcribe_result.transcript_text)
print("\nDiarized:\n", transcribe_result.diarized_transcript_text)

# Generate SOAP
soap_result = _generate_soap(
    transcript_text=transcribe_result.transcript_text, repo_id=None
)
print("\nSOAP Text:\n", soap_result.soap_text)
print("\nSOAP Sections:\n", soap_result.soap)
