# Translytic

Translytic is a Python desktop application that transcribes video speech, translates captions, plays the video with synchronized subtitles, and can generate translated dubbed audio.

## Features

- Video loading through a file picker or drag and drop
- Speech transcription using OpenAI Whisper
- Automatic CPU/CUDA selection when PyTorch supports it
- Translation and dubbing to Hindi, Marathi, and German
- Google Translate fallback through `deep-translator`
- Optional OpenRouter translation configured through environment variables or a local `.env` file
- Synced caption playback, seeking, and original/dubbed audio switching
- SRT subtitle export
- Translation failure warnings; failed segments retain source text in captions and are skipped by TTS

## Requirements

- Python 3.10.5 is supported by the current tested environment; Python 3.11.x is also recommended for a new installation
- FFmpeg and FFprobe installed and available on `PATH`
- Internet access for online translation and Edge TTS
- Enough temporary disk space for extracted audio and dubbed output
- NVIDIA GPU and a compatible CUDA-enabled PyTorch build for GPU acceleration (optional)

Whisper can run on CPU, but processing long videos may be slow.

## Install on Windows

Clone the repository and enter the project directory:

```powershell
git clone https://github.com/Soham-1009/Translytic.git
cd Translytic
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, activate the environment using a permitted execution policy or run `.venv\Scripts\python.exe` directly.

Install FFmpeg separately and confirm both tools are available:

```powershell
ffmpeg -version
ffprobe -version
```

For GPU acceleration, install a PyTorch build compatible with your NVIDIA driver using the official PyTorch installation selector. Then verify the result:

```powershell
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU mode')"
```

## Configure optional OpenRouter translation

Create a key at [OpenRouter API Keys](https://openrouter.ai/settings/keys). The project includes a `.env` file with a placeholder. Replace it with your own key:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=openrouter/free
```

`openrouter/free` is OpenRouter's free-model router. It automatically selects an available free model, so the exact model may vary. Free endpoints can be rate-limited or temporarily unavailable. If you prefer a specific model, choose a currently available model marked free in the [OpenRouter model catalog](https://openrouter.ai/models?max_price=0) and set its exact model ID in `OPENROUTER_MODEL`. Avoid paid model IDs if you need to keep inference free.

The app loads `.env` at startup. The `.env` file is ignored by Git; do not commit your real key. If no OpenRouter key is configured, Translytic uses Google Translate. If an OpenRouter request fails, the app attempts the Google Translate fallback. If both providers fail for a segment, the source text is retained and a warning is written to the processing log. Dubbed audio skips segments explicitly marked as translation failures.

## Run

```powershell
python app.py
```

1. Select or drop a video with an audio track.
2. Select Hindi, Marathi, or German as the target language.
3. Click **Process video**.
4. Wait while audio is extracted, transcribed, translated, and dubbed.
5. Review the captions and playback.
6. Use **Export .srt** to save translated captions.

During dubbing, Translytic fetches Edge TTS's current voice catalog and validates
the selected voice against the target locale. It then generates MP3 segments,
validates them with FFprobe, normalizes them to a 44.1 kHz stereo WAV timeline,
and only enables the Original/Dubbed switch after the final WAV is validated.
If a segment fails, later segments continue; segments marked as translation
failures are skipped. When valid dubbed audio is generated, playback starts in
Dubbed mode and the button switches between Dubbed and Original audio.

Supported extensions in the UI include MP4, MOV, AVI, MKV, and WebM. Actual codec support depends on the FFmpeg/OpenCV installation.

## Tests

The subtitle utility tests do not require Whisper, a GUI, or network access:

```powershell
python -m unittest discover -s tests -v
```

## Known limitations

- Translation and voice synthesis require network access.
- Machine translation may need manual review for idioms, names, and technical vocabulary.
- Dubbed speech length can differ from the original dialogue timing. A segment is
  placed between its timestamp and the next translated segment; the implementation
  attempts up to 1.5x time compression and only truncates the tail as a last
  resort, with a warning in the processing log.
- Edge TTS voice discovery and synthesis require outbound network access. A
  temporary provider/network failure disables dubbed audio for that run without
  disabling subtitles.
- Google Translate fallback requests are paced, cached within a processing run,
  and retried when rate-limited. If Google continues returning HTTP 429, wait and
  retry later. When Whisper identifies the source language, the app also tries
  the free MyMemory backend before retaining source text. You can alternatively
  configure the optional OpenRouter provider in `.env`; without a successful
  translation provider, translated subtitles and dubbing cannot be generated safely.
- A full visual subtitle editor, speaker diarization, resumable processing, and additional subtitle formats are not yet implemented.
- Python dependency versions are not pinned; for a reproducible release, test and lock versions on the target Windows/Python environment.

## Temporary files and privacy

Temporary audio files created by the current application instance are tracked and cleaned up on shutdown. Translytic no longer deletes every file matching a broad pattern in the shared system temporary directory. Do not commit API keys, `.env`, virtual environments, media files, or generated audio.
