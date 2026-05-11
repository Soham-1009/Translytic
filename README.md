# Translytic

Translytic is a Python desktop application that turns a video into translated captions and plays the video back with synced subtitles. It can also generate a dubbed audio track from the translated text and export the translated captions as an `.srt` file.

The app is built with Tkinter, OpenCV, pygame, Whisper, MoviePy, deep-translator, edge-tts, and pydub.

## Features

- Modern Tkinter desktop UI with drag-and-drop video loading
- Video preview and fullscreen-friendly playback area
- Audio extraction from video files
- Speech transcription using OpenAI Whisper
- Caption confidence logging for Whisper segments
- Translation to English, Hindi, Marathi, Spanish, French, German, Japanese, Chinese, Arabic, and Portuguese
- Google Translate fallback through `deep-translator`
- Optional OpenAI-powered natural translation if an API key is added in `app.py`
- Synced live captions during playback
- Original audio / dubbed audio toggle
- Dubbed audio generation using edge-tts
- Subtitle export in `.srt` format
- Keyboard shortcuts for play/pause and seeking
- Automatic cleanup of temporary audio files

## Supported Video Formats

The file picker and drag-and-drop loader accept:

- `.mp4`
- `.mov`
- `.avi`
- `.mkv`
- `.webm`

## Requirements

- Python 3.11.9
- FFmpeg and FFprobe installed and available in PATH
- Internet connection for Google Translate and edge-tts
- Enough disk space for temporary extracted audio files

Whisper can run on CPU, but transcription may be slow for long videos.

## Installation

Clone the repository:

```powershell
git clone https://github.com/Soham-1009/Translytic.git
cd Translytic
```

Create and activate a virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
```

Install dependencies:

```powershell
pip install pygame opencv-python Pillow openai-whisper deep-translator moviepy tkinterdnd2 openai edge-tts pydub
```

If you have an NVIDIA GPU and want Whisper to use GPU acceleration, install the CUDA-enabled PyTorch build inside the activated virtual environment:

```powershell
pip uninstall torch torchvision torchaudio -y
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

Check whether PyTorch can see your GPU:

```powershell
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

Install FFmpeg and make sure both `ffmpeg` and `ffprobe` work from the terminal:

```powershell
ffmpeg -version
ffprobe -version
```

## Usage

Run the app:

```powershell
python app.py
```

Basic workflow:

1. Click **Browse** or drag a video file into the app.
2. Select the target language.
3. Click **Process & Play**.
4. Wait for audio extraction, transcription, translation, and dubbed audio generation.
5. Preview the video with translated captions.
6. Use **Original / Dubbed** to switch audio mode when dubbed audio is available.
7. Click **Export .srt** to save translated subtitles.

## Controls

- Click the video area to play or pause.
- Use the playback buttons to play, pause, and stop.
- Use the seek bar to jump through the video.
- Press `Space` to play or pause.
- Press `Left Arrow` to seek backward 5 seconds.
- Press `Right Arrow` to seek forward 5 seconds.

## How It Works

1. MoviePy extracts the source audio into a temporary WAV file.
2. Whisper transcribes the audio into timestamped text segments.
3. Each segment is translated into the selected language.
4. edge-tts creates translated speech clips for each segment.
5. pydub overlays the generated speech clips onto a silent audio track.
6. OpenCV decodes video frames in a background thread.
7. pygame plays either the original extracted audio or the generated dubbed audio.
8. Tkinter displays the video frames, captions, progress, and logs.

## Optional OpenAI Translation

By default, the app uses `deep-translator` with Google Translate. The code also supports OpenAI translation if you set this variable in `app.py`:

```python
OPENAI_API_KEY = "your-api-key"
```

If OpenAI translation fails, the app falls back to Google Translate automatically.

## Notes

- The app auto-installs missing Python packages when it starts, but installing them manually is recommended.
- FFmpeg and FFprobe are required. The app exits with an error message if either tool is not found.
- Videos without audio cannot be processed.
- Temporary files are created in the system temp folder and cleaned up when the app closes.
- Do not commit `venv/`, generated audio, cache files, or large videos to GitHub.
