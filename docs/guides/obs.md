# OBS on Linux

## Install

| Source | When |
| --- | --- |
| **Flathub** (`com.obsproject.Studio`) | Recommended: follows OBS releases, includes the browser source, plugins available as Flatpak extensions |
| Distribution package | Fine if recent (OBS 30 or later). Ubuntu users can use the official PPA `ppa:obsproject/obs-studio` |

Avoid having both: scenes and settings are not shared, and you will edit the wrong one.
`tuxcast doctor` warns when both are installed.

## Encoder

Encode on your GPU; x264 on the CPU costs frames in demanding games.

| GPU | Encoder in OBS | Notes |
| --- | --- | --- |
| NVIDIA | **NVENC H.264** (or HEVC/AV1 for YouTube) | Needs the proprietary driver. Preset *P5*, tuning *High Quality* |
| AMD | **FFmpeg VAAPI H.264** / *Hardware (VA-API)* | Needs `mesa-va-drivers` (Debian/Ubuntu) or `mesa-va-drivers-freeworld` (Fedora) |
| Intel | **QuickSync H.264** or VA-API | Needs `intel-media-va-driver-non-free` (Debian/Ubuntu) |
| none | x264, preset *veryfast* | |

Check that VA-API can encode with `vainfo`: the list must contain `VAEntrypointEncSlice`.

### Settings for Twitch

| Setting | Value |
| --- | --- |
| Rate control | CBR |
| Bitrate | 6000 kbps for 1080p60, 4500 kbps for 720p60 |
| Keyframe interval | 2 s |
| Resolution | 1920×1080 at 60 fps, or 1280×720 if your upload is under 8 Mb/s |

YouTube accepts higher bitrates and other codecs (HEVC, AV1); Twitch remains the
constraint when you multistream.

## Capture

| Source | Use it for |
| --- | --- |
| *Screen Capture (PipeWire)* | A whole screen, on Wayland or X11 |
| *Window Capture (PipeWire)* | One window, on Wayland |
| *Game Capture* ([obs-vkcapture](https://github.com/nowrep/obs-vkcapture)) | Vulkan and OpenGL games, with lower overhead and no portal prompt. Launch games with `obs-gamecapture %command%` in Steam |
| *Audio Output Capture* | A PipeWire sink: your desktop, or a [tuxcast sink](audio.md) |
| *Application Audio Capture* ([obs-pipewire-audio-capture](https://github.com/dimtpap/obs-pipewire-audio-capture)) | One app's sound, without virtual sinks |

## Multistream

The [obs-multi-rtmp](https://github.com/sorayuki/obs-multi-rtmp) plugin adds a dock with one
output per platform (Twitch, YouTube, TikTok…), each with its own encoder settings if needed.
Share the encoder when platforms accept the same settings, to save GPU time.

## obs-websocket

Stream Deck apps and automation control OBS through obs-websocket, built into OBS since 28.
**Tools → WebSocket Server Settings**: enable the server and keep authentication on. Without
a password, any program on your network can start your stream. `tuxcast doctor` checks both.
