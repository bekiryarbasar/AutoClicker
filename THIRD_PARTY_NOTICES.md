# Third-party notices

## FFmpeg

AutoClicker optionally downloads and runs FFmpeg as a separate process for local video background playback. It is not linked into AutoClicker's Python executable.

- Version: FFmpeg 9.0.2, Windows x86-64 essentials build distributed through `imageio-ffmpeg` 0.8.1.
- License: GPL-3.0-or-later for this build because it enables GPL components including x264. FFmpeg itself is generally LGPL; this particular configured binary is GPL.
- Binary source and pinned SHA-256: <https://github.com/imageio/imageio-ffmpeg/blob/v0.8.1/tools/ffmpeg-sources.json> (the `windows-x86_64` entry).
- Corresponding FFmpeg source revision: <https://github.com/FFmpeg/FFmpeg/tree/946fcce07b>.
- Windows build source/configuration: <https://github.com/GyanD/codexffmpeg/releases/tag/9.0.2>.
- GPL license text: <https://www.gnu.org/licenses/gpl-3.0.txt>.

The optional binary is distributed separately in `AutoClicker-VideoRuntime.zip`, not inside `AutoClicker.exe`. The archive includes `FFmpeg-NOTICE.txt` with license and source links. FFmpeg is downloaded only after the user chooses a video and confirms.

## Pillow

Pillow is used to display decoded video frames and is licensed under the MIT-CMU License: <https://github.com/python-pillow/Pillow/blob/13.0.0/LICENSE>.
