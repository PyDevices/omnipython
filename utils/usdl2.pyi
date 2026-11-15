# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""An SDL2 subset for Python: the pure-Python fallback for the native `usdl2` module."""

from collections.abc import Callable
from typing import Any

_Buffer = bytes | bytearray | memoryview

SDL_WINDOWPOS_UNDEFINED: int
SDL_WINDOWPOS_CENTERED: int
SDL_WINDOW_FULLSCREEN: int
SDL_WINDOW_OPENGL: int
SDL_WINDOW_SHOWN: int
SDL_WINDOW_HIDDEN: int
SDL_WINDOW_BORDERLESS: int
SDL_WINDOW_RESIZABLE: int
SDL_WINDOW_MINIMIZED: int
SDL_WINDOW_MAXIMIZED: int
SDL_WINDOW_INPUT_GRABBED: int
SDL_WINDOW_INPUT_FOCUS: int
SDL_WINDOW_MOUSE_FOCUS: int
SDL_WINDOW_FULLSCREEN_DESKTOP: int
SDL_WINDOW_ALLOW_HIGHDPI: int
SDL_HINT_ORIENTATIONS: str
SDL_WINDOW_MOUSE_CAPTURE: int
SDL_WINDOW_ALWAYS_ON_TOP: int
SDL_WINDOW_SKIP_TASKBAR: int
SDL_WINDOW_UTILITY: int
SDL_WINDOW_TOOLTIP: int
SDL_WINDOW_POPUP_MENU: int
SDL_WINDOW_VULKAN: int
SDL_RENDERER_SOFTWARE: int
SDL_RENDERER_ACCELERATED: int
SDL_RENDERER_PRESENTVSYNC: int
SDL_RENDERER_TARGETTEXTURE: int
SDL_INIT_TIMER: int
SDL_INIT_AUDIO: int
SDL_INIT_VIDEO: int
SDL_INIT_JOYSTICK: int
SDL_INIT_HAPTIC: int
SDL_INIT_GAMECONTROLLER: int
SDL_INIT_EVENTS: int
SDL_INIT_EVERYTHING: int
SDL_INIT_NOPARACHUTE: int
AUDIO_U8: int
AUDIO_S8: int
AUDIO_U16LSB: int
AUDIO_S16LSB: int
AUDIO_U16MSB: int
AUDIO_S16MSB: int
AUDIO_S32LSB: int
AUDIO_S32MSB: int
AUDIO_F32LSB: int
AUDIO_F32MSB: int
AUDIO_U16SYS: int
AUDIO_S16SYS: int
AUDIO_S32SYS: int
AUDIO_F32SYS: int
SDL_TEXTUREACCESS_STATIC: int
SDL_TEXTUREACCESS_STREAMING: int
SDL_TEXTUREACCESS_TARGET: int
SDL_BLENDMODE_NONE: int
SDL_BLENDMODE_BLEND: int
SDL_BLENDMODE_ADD: int
SDL_BLENDMODE_MOD: int
SDL_QUIT: int
SDL_WINDOWEVENT: int
SDL_WINDOWEVENT_CLOSE: int
SDL_KEYDOWN: int
SDL_KEYUP: int
SDL_MOUSEMOTION: int
SDL_MOUSEBUTTONDOWN: int
SDL_MOUSEBUTTONUP: int
SDL_MOUSEWHEEL: int
SDL_FINGERDOWN: int
SDL_FINGERUP: int
SDL_FINGERMOTION: int
SDL_JOYAXISMOTION: int
SDL_JOYBALLMOTION: int
SDL_JOYHATMOTION: int
SDL_JOYBUTTONDOWN: int
SDL_JOYBUTTONUP: int
SDL_JOYDEVICEADDED: int
SDL_JOYDEVICEREMOVED: int
SDL_BUTTON_LMASK: int
SDL_BUTTON_MMASK: int
SDL_BUTTON_RMASK: int
SDL_HAT_CENTERED: int
SDL_HAT_UP: int
SDL_HAT_RIGHT: int
SDL_HAT_DOWN: int
SDL_HAT_LEFT: int

def SDL_DEFINE_PIXELFORMAT(type: int, order: int, layout: int, bits: int, bytes: int) -> int:
    """Define a pixel format."""


SDL_PIXELTYPE_UNKNOWN: int
SDL_PIXELTYPE_INDEX1: int
SDL_PIXELTYPE_INDEX4: int
SDL_PIXELTYPE_INDEX8: int
SDL_PIXELTYPE_PACKED8: int
SDL_PIXELTYPE_PACKED16: int
SDL_PIXELTYPE_PACKED32: int
SDL_PIXELTYPE_ARRAYU8: int
SDL_PIXELTYPE_ARRAYU16: int
SDL_PIXELTYPE_ARRAYU32: int
SDL_PIXELTYPE_ARRAYF16: int
SDL_PIXELTYPE_ARRAYF32: int
SDL_PACKEDORDER_NONE: int
SDL_PACKEDORDER_XRGB: int
SDL_PACKEDORDER_RGBX: int
SDL_PACKEDORDER_ARGB: int
SDL_PACKEDORDER_RGBA: int
SDL_PACKEDORDER_XBGR: int
SDL_PACKEDORDER_BGRX: int
SDL_PACKEDORDER_ABGR: int
SDL_PACKEDORDER_BGRA: int
SDL_ARRAYORDER_NONE: int
SDL_ARRAYORDER_RGB: int
SDL_ARRAYORDER_RGBA: int
SDL_ARRAYORDER_ARGB: int
SDL_ARRAYORDER_BGR: int
SDL_ARRAYORDER_BGRA: int
SDL_ARRAYORDER_ABGR: int
SDL_PACKEDLAYOUT_NONE: int
SDL_PACKEDLAYOUT_332: int
SDL_PACKEDLAYOUT_4444: int
SDL_PACKEDLAYOUT_1555: int
SDL_PACKEDLAYOUT_5551: int
SDL_PACKEDLAYOUT_565: int
SDL_PACKEDLAYOUT_8888: int
SDL_PACKEDLAYOUT_2101010: int
SDL_PACKEDLAYOUT_1010102: int
SDL_BITMAPORDER_NONE: int
SDL_BITMAPORDER_4321: int
SDL_BITMAPORDER_1234: int
SDL_PIXELFORMAT_UNKNOWN: int
SDL_PIXELFORMAT_INDEX1LSB: int
SDL_PIXELFORMAT_INDEX1MSB: int
SDL_PIXELFORMAT_INDEX4LSB: int
SDL_PIXELFORMAT_INDEX4MSB: int
SDL_PIXELFORMAT_INDEX8: int
SDL_PIXELFORMAT_RGB332: int
SDL_PIXELFORMAT_RGB444: int
SDL_PIXELFORMAT_RGB555: int
SDL_PIXELFORMAT_BGR555: int
SDL_PIXELFORMAT_ARGB4444: int
SDL_PIXELFORMAT_RGBA4444: int
SDL_PIXELFORMAT_ABGR4444: int
SDL_PIXELFORMAT_BGRA4444: int
SDL_PIXELFORMAT_ARGB1555: int
SDL_PIXELFORMAT_RGBA5551: int
SDL_PIXELFORMAT_ABGR1555: int
SDL_PIXELFORMAT_BGRA5551: int
SDL_PIXELFORMAT_RGB565: int
SDL_PIXELFORMAT_BGR565: int
SDL_PIXELFORMAT_RGB24: int
SDL_PIXELFORMAT_BGR24: int
SDL_PIXELFORMAT_RGB888: int
SDL_PIXELFORMAT_RGBX8888: int
SDL_PIXELFORMAT_BGR888: int
SDL_PIXELFORMAT_BGRX8888: int
SDL_PIXELFORMAT_ARGB8888: int
SDL_PIXELFORMAT_RGBA8888: int
SDL_PIXELFORMAT_ABGR8888: int
SDL_PIXELFORMAT_BGRA8888: int
SDL_PIXELFORMAT_ARGB2101010: int

def SDL_Rect(x: int = 0, y: int = 0, w: int = 0, h: int = 0) -> bytes:
    """Pack an `SDL_Rect` as bytes."""

def SDL_Point(x: int = 0, y: int = 0) -> bytes:
    """Pack an `SDL_Point` as bytes."""

def SDL_AudioSpec(freq: int = 0, format: int = 0, channels: int = 0, samples: int = 0) -> bytearray:
    """Return a packed `SDL_AudioSpec` with a NULL callback for queued audio."""

class _SubView:
    """A view into an `SDL_Event`'s union payload."""

    def __init__(self, event: SDL_Event, base: int) -> None: ...
    @property
    def windowID(self) -> int: ...
    @property
    def which(self) -> int: ...
    @property
    def touchId(self) -> int: ...
    @property
    def fingerId(self) -> int: ...
    @property
    def state(self) -> int: ...
    @property
    def scancode(self) -> int: ...
    @property
    def sym(self) -> int: ...
    @property
    def mod(self) -> int: ...
    @property
    def axis(self) -> int: ...
    @property
    def ball(self) -> int: ...
    @property
    def hat(self) -> int: ...
    @property
    def event(self) -> int: ...
    @property
    def clicks(self) -> int: ...
    @property
    def direction(self) -> int: ...
    @property
    def repeat(self) -> int: ...
    @property
    def button(self) -> int: ...
    @property
    def xrel(self) -> int: ...
    @property
    def yrel(self) -> int: ...
    @property
    def value(self) -> int: ...
    @property
    def x(self) -> int | float: ...
    @property
    def y(self) -> int | float: ...
    @property
    def dx(self) -> float: ...
    @property
    def dy(self) -> float: ...
    @property
    def pressure(self) -> float: ...
    @property
    def preciseX(self) -> float: ...
    @property
    def preciseY(self) -> float: ...
    @property
    def keysym(self) -> _SubView: ...

class SDL_Event:
    """A 56-byte `SDL_Event` buffer; `SDL_Event()` is zero-filled, `SDL_Event(buf)` copies `buf`."""

    def __new__(cls, event: SDL_Event | _Buffer | None = None) -> SDL_Event: ...
    def __len__(self) -> int: ...
    @property
    def type(self) -> int: ...
    @type.setter
    def type(self, value: int) -> None: ...
    @property
    def timestamp(self) -> int: ...
    @property
    def motion(self) -> _SubView: ...
    key = motion
    button = motion
    wheel = motion
    jaxis = motion
    jball = motion
    jhat = motion
    jbutton = motion
    tfinger = motion
    window = motion

def SDL_GetError() -> str: ...
def SDL_GetKeyName(sym: int) -> str: ...
def SDL_SetHint(name: str | bytes, value: str | bytes) -> int: ...
def SDL_CreateWindow(title: str | bytes, x: int, y: int, w: int, h: int, flags: int) -> int: ...
def SDL_GetWindowSize(window: int) -> tuple[int, int]: ...
def SDL_GetRendererOutputSize(renderer: int) -> tuple[int, int]: ...
def SDL_GetAudioDeviceName(index: int, iscapture: int) -> str | None: ...
def SDL_OpenAudioDevice(
    device: str | bytes | None,
    iscapture: int,
    desired: _Buffer,
    obtained: bytearray | memoryview | None,
    allowed_changes: int,
) -> int: ...
def SDL_QueueAudio(device: int, data: _Buffer, length: int) -> int: ...
def SDL_DequeueAudio(device: int, data: bytearray | memoryview, length: int) -> int: ...

class _TimerCallback:
    """Opaque token returned by `SDL_TimerCallback`; only usable with `SDL_AddTimer`."""

    callback: Callable[[int, Any], object]
    def __init__(self, callback: Callable[[int, Any], object]) -> None: ...

def SDL_TimerCallback(callback: Callable[[int, Any], object]) -> _TimerCallback: ...
def SDL_AddTimer(interval: int, tcb: _TimerCallback, user_param: Any) -> int: ...
def SDL_RemoveTimer(timer: int) -> int: ...
def SDL_PumpEvents() -> None: ...
def SDL_PollEvent(event: SDL_Event | bytearray | memoryview) -> bool: ...
def SDL_UpdateTexture(texture: int, rect: _Buffer | None, pixels: _Buffer, pitch: int) -> int: ...
def SDL_RenderReadPixels(
    renderer: int, rect: _Buffer | None, format: int, pixels: bytearray | memoryview, pitch: int
) -> None: ...
def SDL_GetDisplayUsableBounds(display_index: int, rect: bytearray | memoryview | None = None) -> int: ...
def SDL_GetDesktopDisplayMode(display_index: int, mode: bytearray | memoryview | None = None) -> int: ...
