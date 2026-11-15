# mp4mux

Record H.264 video and 16-bit PCM sound into an MP4 file that plays
everywhere. Hand the writer each frame from an encoder and each block from a
microphone, with the time each was captured, and close it when you stop.
Pure Python, for MicroPython, CircuitPython and CPython.

```python
import mp4mux

mp4 = mp4mux.Writer("/sd/clip.mp4", 1280, 720, fps_hint=25, audio_rate=16000)
mp4.add_video(access_unit, pts_ms, keyframe)   # Annex B, as h264enc gives it
mp4.add_audio(pcm_block, pts_ms)               # 16-bit little-endian
mp4.close()                                    # writes the index
```

[`examples/mp4mux_simpletest.py`](examples/mp4mux_simpletest.py) writes two
seconds of a tone, which runs anywhere and prints `tone.mp4: 2000 ms of sound`.

## Recording on an ESP32-P4

The shape of a recording loop, with the camera, the P4's hardware encoder
(`h264enc`) and the board's microphone. It hasn't been run on a board yet,
so measure the frame rate it keeps before you rely on it.

```python
import time
import board_config
import h264enc
import mp4mux

camera = board_config.camera()              # set up for 1280x720 RGB565
mic = board_config.pcm_in().open()          # 16 kHz, 16-bit mono
encoder = h264enc.Encoder(1280, 720, fps=25, gop=25)
mp4 = mp4mux.Writer("/sd/clip.mp4", 1280, 720, fps_hint=25)
block = bytearray(640)                      # 20 ms of sound
start = time.ticks_ms()
heard_ms = 0
while time.ticks_diff(time.ticks_ms(), start) < 60_000:
    frame = camera.frame()
    if frame is not None:
        now = time.ticks_diff(time.ticks_ms(), start)
        mp4.add_video(encoder.encode(frame), now, encoder.keyframe)
    while heard_ms < time.ticks_diff(time.ticks_ms(), start):
        n = mic.readinto(block)
        mp4.add_audio(memoryview(block)[:n], heard_ms)
        heard_ms += n // 32                 # 32 bytes a millisecond
mp4.close()
```

Both tracks take their times from one clock, so they stay in step. The sound
is timed by the samples it holds rather than by when the read returned, so a
read that comes late doesn't open a gap; a block whose time runs more than
40 ms past the sound before it is padded with silence, so a dropped read
doesn't pull the picture out of step either.

## What goes in the file

The video track is H.264 as `avc1`. Each access unit's start codes become
length prefixes, and the first SPS and PPS go into the track's `avcC` box.
Frames before the first keyframe are dropped, since nothing could decode
them. Each frame keeps the time it was given, so a frame rate that varies
plays back at the speed it was recorded; `fps_hint` only sizes the tables
and sets the last frame's length. Frames are stored in the order they're
given, which is right for an encoder without B-frames, the P4's included.

The sound track is 16-bit little-endian PCM as `sowt`, which ffmpeg, VLC and
Windows read. `add_audio` takes bytes, a bytearray, a memoryview or an
`array("h")`. A track that starts after the other gets an edit list, so
players start it at the right moment.

ffprobe reads the files and ffmpeg decodes them with no errors, plain,
fragmented and past 4 GB; the tests check every frame's time, the
keyframes, and the silence in a gap. Playback
in VLC and Windows' own player hasn't been checked.

## Memory, power loss and limits

The index stays in RAM until `close()`: about 12 bytes a frame and 8 a block
of sound, preallocated for `max_seconds` (10 minutes by default) and grown
past it. Ten minutes at 25 fps with 20 ms blocks of sound is about 420 KB.

If power is lost before `close()`, the file holds its media but no index,
and players refuse it. Pass `fragment_ms` to write a fragmented MP4
instead, and a recording cut off anywhere still plays up to its last whole
fragment:

```python
mp4 = mp4mux.Writer("/sd/clip.mp4", 1280, 720, fps_hint=25, fragment_ms=2000)
```

Each fragment is written once that many milliseconds have gathered, at the
next keyframe, so make the encoder's keyframe interval no longer than the
fragment. The fragment being gathered stays in RAM, media and all: about
two seconds of video and sound at that setting. Start both tracks
before the first fragment is written: the file's tracks are the ones that
had started by then, and a frame or a block for a track that hadn't raises
`ValueError`.

A file may pass 4 GB: its media goes into a second `mdat` box and its
offsets into `co64`. A FAT card stops any file at
4 GB, so the write raises `OSError` there; exFAT goes past it.

This is a preview: it isn't released yet, and the names may still change.
