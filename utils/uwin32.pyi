# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A Win32 subset for CPython and MicroPython on Windows: windows, GDI, timers, WASAPI, MIDI and device enumeration.

Importing it anywhere but Windows raises `ImportError`.
"""

from collections.abc import Callable
from typing import Any

_Buffer = bytes | bytearray | memoryview

CS_HREDRAW: int
CS_VREDRAW: int
CW_USEDEFAULT: int
IDC_ARROW: int
COLOR_WINDOW: int
SW_SHOW: int
SW_MAXIMIZE: int
SW_HIDE: int
PM_REMOVE: int
ERROR_CLASS_ALREADY_EXISTS: int
WS_OVERLAPPED: int
WS_CAPTION: int
WS_SYSMENU: int
WS_MINIMIZEBOX: int
WS_MAXIMIZEBOX: int
WS_VISIBLE: int
WS_CLIPCHILDREN: int
WS_CLIPSIBLINGS: int
WS_DISPLAY: int
WM_DESTROY: int
WM_CLOSE: int
WM_QUIT: int
WM_PAINT: int
WM_KEYDOWN: int
WM_KEYUP: int
WM_SYSKEYDOWN: int
WM_SYSKEYUP: int
WM_MOUSEMOVE: int
WM_LBUTTONDOWN: int
WM_LBUTTONUP: int
WM_RBUTTONDOWN: int
WM_RBUTTONUP: int
WM_MBUTTONDOWN: int
WM_MBUTTONUP: int
WM_MOUSEWHEEL: int
WM_MOUSEHWHEEL: int
MK_LBUTTON: int
MK_RBUTTON: int
MK_MBUTTON: int
WHEEL_DELTA: int
VK_BACK: int
VK_TAB: int
VK_RETURN: int
VK_SHIFT: int
VK_CONTROL: int
VK_MENU: int
VK_ESCAPE: int
VK_SPACE: int
VK_PRIOR: int
VK_NEXT: int
VK_END: int
VK_HOME: int
VK_LEFT: int
VK_UP: int
VK_RIGHT: int
VK_DOWN: int
VK_INSERT: int
VK_DELETE: int
VK_LSHIFT: int
VK_RSHIFT: int
VK_LCONTROL: int
VK_RCONTROL: int
VK_LMENU: int
VK_RMENU: int
VK_LWIN: int
VK_RWIN: int
VK_F1: int
BI_RGB: int
BI_BITFIELDS: int
DIB_RGB_COLORS: int
SRCCOPY: int
SPI_GETWORKAREA: int
DPI_AWARENESS_CONTEXT_UNAWARE: int
DPI_AWARENESS_CONTEXT_SYSTEM_AWARE: int
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE: int
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2: int
CLR_INVALID: int
RGB565_MASKS: tuple[int, int, int]
MEM_COMMIT: int
MEM_RESERVE: int
MEM_RELEASE: int
PAGE_READWRITE: int
INFINITE: int
CREATE_WAITABLE_TIMER_HIGH_RESOLUTION: int
TIMER_ALL_ACCESS: int
WT_EXECUTEDEFAULT: int
COINIT_MULTITHREADED: int
COINIT_APARTMENTTHREADED: int
CLSCTX_ALL: int
S_OK: int
S_FALSE: int
RPC_E_CHANGED_MODE: int
eRender: int
eCapture: int
eConsole: int
AUDCLNT_SHAREMODE_SHARED: int
AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM: int
AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY: int
WAVE_FORMAT_PCM: int
KMOD_LSHIFT: int
KMOD_RSHIFT: int
KMOD_LCTRL: int
KMOD_RCTRL: int
KMOD_LALT: int
KMOD_RALT: int
KMOD_LGUI: int
KMOD_RGUI: int
SWP_NOZORDER: int
SWP_NOACTIVATE: int
CM_GETIDLIST_FILTER_ENUMERATOR: int
CM_GETIDLIST_FILTER_PRESENT: int
CM_GETIDLIST_FILTER_PRESENT_ENUMERATOR: int
CM_DRP_DEVICEDESC: int
CM_DRP_COMPATIBLEIDS: int
CM_DRP_SERVICE: int
CM_DRP_FRIENDLYNAME: int
MAX_DEVICE_ID_LEN: int
MMSYSERR_NOERROR: int
CALLBACK_NULL: int
CALLBACK_WINDOW: int
MM_MIM_OPEN: int
MM_MIM_CLOSE: int
MM_MIM_DATA: int
MM_MIM_LONGDATA: int
MM_MIM_ERROR: int
MM_MIM_LONGERROR: int
MM_MOM_OPEN: int
MM_MOM_CLOSE: int
MM_MOM_DONE: int
MHDR_DONE: int
MHDR_PREPARED: int
MHDR_INQUEUE: int
MIDIERR_STILLPLAYING: int
MIDIOUTCAPS_SIZE: int
MIDIINCAPS_SIZE: int
user32: Any
gdi32: Any
kernel32: Any
ole32: Any
winmm: Any
cfgmgr32: Any

BOOL = int
DWORD = int
WORD = int
LONG = int
ULONG = int
HWND = int
HDC = int
HINSTANCE = int
HMENU = int
HICON = int
HCURSOR = int
HBRUSH = int
HBITMAP = int
HANDLE = int
LPARAM = int
WPARAM = int
UINT = int
LPCWSTR = str
LPWSTR = str
ATOM = int
BYTE = int
WCHAR = str
HRESULT = int
INT = int
UINT32 = int
INT64 = int
UINT64 = int
LRESULT = int
LPVOID = int
LPCVOID = int

# Struct classes. On CPython they are `ctypes.Structure`s; on MicroPython they wrap a buffer.

class POINT:
    def __init__(self, x: int = 0, y: int = 0, buf: Any = None, offset: int = 0) -> None: ...
    x: int
    y: int

class RECT:
    def __init__(self, left: int = 0, top: int = 0, right: int = 0, bottom: int = 0, buf: Any = None, offset: int = 0) -> None: ...
    left: int
    top: int
    right: int
    bottom: int

class MSG:
    def __init__(self) -> None: ...
    hwnd: int
    message: int
    wParam: int
    lParam: int
    time: int
    pt: POINT

class WNDCLASSEXW:
    def __init__(self) -> None: ...
    cbSize: int
    style: int
    lpfnWndProc: Any
    cbClsExtra: int
    cbWndExtra: int
    hInstance: int
    hIcon: int
    hCursor: int
    hbrBackground: int
    lpszMenuName: str | None
    lpszClassName: str | None
    hIconSm: int

class PAINTSTRUCT:
    def __init__(self) -> None: ...
    hdc: int
    fErase: int
    rcPaint: RECT
    fRestore: int
    fIncUpdate: int

class BITMAPINFOHEADER:
    def __init__(self, buf: Any = None, offset: int = 0) -> None: ...
    biSize: int
    biWidth: int
    biHeight: int
    biPlanes: int
    biBitCount: int
    biCompression: int
    biSizeImage: int
    biXPelsPerMeter: int
    biYPelsPerMeter: int
    biClrUsed: int
    biClrImportant: int

class BITMAPINFO:
    def __init__(self) -> None: ...
    bmiHeader: BITMAPINFOHEADER

class GUID:
    def __init__(self, d1: int = 0, d2: int = 0, d3: int = 0, d4: Any = None) -> None: ...
    Data1: int
    Data2: int
    Data3: int
    Data4: Any

class WAVEFORMATEX:
    def __init__(self) -> None: ...
    wFormatTag: int
    nChannels: int
    nSamplesPerSec: int
    nAvgBytesPerSec: int
    nBlockAlign: int
    wBitsPerSample: int
    cbSize: int

CLSID_MMDeviceEnumerator: GUID
IID_IMMDeviceEnumerator: GUID
IID_IAudioClient: GUID
IID_IAudioRenderClient: GUID
IID_IAudioCaptureClient: GUID
MIDIHDR_SIZE: int

def byref(obj: Any) -> Any: ...
def sizeof(obj: Any) -> int: ...
def memmove(dst: int, src: _Buffer | int, count: int) -> Any:
    """Copy `count` bytes to address `dst`; unlike `ctypes.memmove` `src` may be a bytearray or memoryview."""
def string_at(ptr: int, size: int = -1) -> bytes: ...
def WNDPROC(fn: Callable[[int, int, int, int], int]) -> Any:
    """Wrap a window procedure `(hwnd, msg, wparam, lparam) -> int` as a C callback."""
def TIMERAPCROUTINE(fn: Callable[[Any, int, int], None] | None = None) -> Any:
    """Wrap a timer APC routine as a C callback; with no argument, a no-op callback."""

def GET_X_LPARAM(lparam: int) -> int: ...
def GET_Y_LPARAM(lparam: int) -> int: ...
def GET_WHEEL_DELTA_WPARAM(wparam: int) -> int: ...
def MAKEINTRESOURCE(value: int) -> Any: ...
def hwnd_int(hwnd: Any) -> int: ...
def GetLastError() -> int: ...
def DefWindowProcW(hwnd: int, msg: int, wparam: int, lparam: int) -> int: ...
def GetModuleHandleW(name: str | None = None) -> int: ...
def LoadCursorW(instance: int | None, cursor: int | str) -> int: ...
def RegisterClassExW(cls: WNDCLASSEXW) -> int: ...
def CreateWindowExW(
    ex_style: int,
    class_name: str,
    window_name: str,
    style: int,
    x: int,
    y: int,
    width: int,
    height: int,
    parent: int | None = None,
    menu: int | None = None,
    instance: int | None = None,
    param: int | None = None,
) -> int: ...
def DestroyWindow(hwnd: int) -> bool: ...
def ShowWindow(hwnd: int, cmd: int = ...) -> bool: ...
def UpdateWindow(hwnd: int) -> bool: ...
def GetClientRect(hwnd: int) -> tuple[int, int, int, int]:
    """Return `(left, top, right, bottom)`, or all zeros on failure."""
def GetWindowRect(hwnd: int) -> tuple[int, int, int, int]:
    """Return `(left, top, right, bottom)`, or all zeros on failure."""
def AdjustWindowRectEx(width: int, height: int, style: int, ex_style: int = 0) -> tuple[int, int]:
    """Return the outer `(width, height)` of a window whose client area is `width` by `height`."""
def SetWindowPos(hwnd: int, x: int, y: int, width: int, height: int, flags: int = ...) -> bool: ...
def GetDC(hwnd: int) -> int: ...
def ReleaseDC(hwnd: int, hdc: int) -> int: ...
def BeginPaint(hwnd: int) -> tuple[int, PAINTSTRUCT]: ...
def EndPaint(hwnd: int, ps: PAINTSTRUCT) -> bool: ...
def InvalidateRect(hwnd: int, erase: bool = False) -> bool: ...
def ValidateRect(hwnd: int) -> bool: ...
def PeekMessageW(hwnd: int | None = None, remove: bool = True) -> MSG | None: ...
def TranslateMessage(msg: MSG) -> bool: ...
def DispatchMessageW(msg: MSG) -> int: ...
def PostQuitMessage(code: int = 0) -> None: ...
def PostMessageW(hwnd: int, msg: int, wparam: int = 0, lparam: int = 0) -> bool: ...
def GetMessageW(hwnd: int | None = None, min_msg: int = 0, max_msg: int = 0) -> tuple[int, MSG]: ...
def ScreenToClient(hwnd: int, x: int, y: int) -> tuple[int, int]: ...
def GetAsyncKeyState(vk: int) -> int: ...
def MapVirtualKeyW(code: int, map_type: int = 0) -> int: ...
def SystemParametersInfoW_GETWORKAREA() -> tuple[int, int, int, int]:
    """Return the work area as `(left, top, width, height)`, or all zeros on failure."""
def SetProcessDpiAwarenessContext(context: int = ...) -> bool | None:
    """Declare the process's DPI awareness; `None` on a Windows that lacks the call."""
def SetProcessDPIAware() -> bool:
    """System-wide DPI awareness, for Windows older than 10 1703."""
def bmi_bgra(width: int, height: int) -> BITMAPINFO:
    """32-bit top-down `BITMAPINFO` for BGRA pixels."""
def bmi_rgb565(width: int, height: int) -> BITMAPINFO:
    """16-bit top-down `BITMAPINFO` for little-endian RGB565 pixels; `width` must be even."""
def dib_bits(buf: bytearray | memoryview) -> int:
    """Address of `buf`, to hand GDI as its `bits` argument."""
def VirtualAlloc(size: int, protect: int = ...) -> int:
    """Reserve and commit `size` bytes; return the base address, or 0 on failure."""
def VirtualFree(ptr: int) -> bool: ...
def buffer_at(ptr: int, size: int) -> memoryview:
    """Writable view of `size` bytes at address `ptr`."""
def GetPixel(hdc: int, x: int, y: int) -> int:
    """Return the `0x00BBGGRR` color at (`x`, `y`), or `CLR_INVALID`."""
def StretchDIBits(
    hdc: int,
    dest_w: int,
    dest_h: int,
    src_w: int,
    src_h: int,
    bits: int,
    bmi: BITMAPINFO,
    *,
    dest_x: int = 0,
    dest_y: int = 0,
) -> int: ...
def SetDIBitsToDevice(
    hdc: int,
    x_dst: int,
    y_dst: int,
    width: int,
    height: int,
    x_src: int,
    y_src: int,
    start_scan: int,
    scan_lines: int,
    bits: int,
    bmi: BITMAPINFO,
) -> int: ...
def GetKeyNameTextW(lparam: int) -> str: ...
def SetWindowTextW(hwnd: int, text: str) -> bool: ...
def GetWindowLongPtrW(hwnd: int, index: int) -> int: ...
def SetWindowLongPtrW(hwnd: int, index: int, new_long: int) -> int: ...
def modifier_mask() -> int:
    """SDL-style `KMOD_*` mask from `GetAsyncKeyState`."""
def virtual_key_to_sdl(vk: int) -> int:
    """Map a Win32 virtual-key code to an SDL keycode."""
def CreateWaitableTimerExW(manual_reset: bool = False, high_resolution: bool = False) -> int: ...
def SetWaitableTimer(
    handle: int, due_ms: int, period_ms: int, apc: Any = None, arg: Any = None
) -> int: ...
def CancelWaitableTimer(handle: int) -> bool: ...
def CloseHandle(handle: int) -> bool: ...
def SleepEx(ms: int, alertable: bool = True) -> int: ...
def WaitForSingleObjectEx(handle: int, ms: int, alertable: bool = True) -> int: ...
def SUCCEEDED(hr: int) -> bool: ...
def IUnknown_AddRef(punk: int) -> int: ...
def IUnknown_Release(punk: int) -> int: ...
def CoInitializeEx(flags: int = ...) -> int: ...
def CoUninitialize() -> None: ...
def CoCreateInstance(clsid: GUID, iid: GUID) -> int: ...
def MMDeviceEnumerator_Create() -> int: ...
def IMMDeviceEnumerator_GetDefaultAudioEndpoint(enumerator: int, data_flow: int, role: int = ...) -> int: ...
def IMMDevice_Activate_IAudioClient(device: int) -> int: ...
def WAVEFORMATEX_pcm(rate: int, channels: int, bits: int) -> WAVEFORMATEX: ...
def IAudioClient_Initialize_shared_pcm(client: int, fmt: WAVEFORMATEX, buffer_ms: int) -> None: ...
def IAudioClient_GetBufferSize(client: int) -> int: ...
def IAudioClient_GetCurrentPadding(client: int) -> int: ...
def IAudioClient_Start(client: int) -> None: ...
def IAudioClient_Stop(client: int) -> None: ...
def IAudioClient_Reset(client: int) -> None: ...
def IAudioClient_GetService(client: int, iid: GUID) -> int: ...
def IAudioRenderClient_GetBuffer(render: int, frames: int) -> int: ...
def IAudioRenderClient_ReleaseBuffer(render: int, frames: int, flags: int = 0) -> None: ...
def IAudioCaptureClient_GetNextPacketSize(capture: int) -> int: ...
def IAudioCaptureClient_GetBuffer(capture: int) -> tuple[int, int, int]:
    """Return `(data_address, frames, flags)`."""
def IAudioCaptureClient_ReleaseBuffer(capture: int, frames: int) -> None: ...
def CM_Get_Device_ID_List(enumerator: str = "USB") -> list[str]:
    """Device instance IDs under an enumerator."""
def CM_Get_DevNode_Registry_Property(instance_id: str, prop: int) -> str | list[str] | None:
    """One registry property of a device node; a list for `CM_DRP_COMPATIBLEIDS`, else a string or `None`."""
def CM_Get_Parent_Device_ID(instance_id: str) -> str | None: ...
def midiOutGetNumDevs() -> int: ...
def midiInGetNumDevs() -> int: ...
def midiOutGetDevName(index: int) -> str: ...
def midiInGetDevName(index: int) -> str: ...
def midiOutOpen(index: int) -> int: ...
def midiOutShortMsg(handle: int, status: int, data1: int = 0, data2: int = 0) -> int: ...
def midiOutReset(handle: int) -> int: ...
def midiOutClose(handle: int) -> int: ...
def midiInOpen(index: int, hwnd: int | None) -> int: ...
def midiInStart(handle: int) -> int: ...
def midiInStop(handle: int) -> int: ...
def midiInReset(handle: int) -> int: ...
def midiInClose(handle: int) -> int: ...
def midi_unpack(lparam: int) -> tuple[int, int, int]:
    """Unpack an `MM_MIM_DATA` lParam into `(status, data1, data2)`."""
def midihdr_init(hdr: int, data: int, length: int) -> None: ...
def midihdr_recorded(hdr: int) -> int: ...
def midihdr_flags(hdr: int) -> int: ...
def midiOutPrepareHeader(handle: int, hdr: int) -> int: ...
def midiOutUnprepareHeader(handle: int, hdr: int) -> int: ...
def midiOutLongMsg(handle: int, hdr: int) -> int: ...
def midiInPrepareHeader(handle: int, hdr: int) -> int: ...
def midiInUnprepareHeader(handle: int, hdr: int) -> int: ...
def midiInAddBuffer(handle: int, hdr: int) -> int: ...
