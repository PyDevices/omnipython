# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from _typeshed import Incomplete
from audiodev import AudioFormat as AudioFormat, PCMInput as PCMInput, PCMOutput as PCMOutput, check_latency as check_latency
from audiodev.bytequeue import ByteQueue as ByteQueue

DEFAULT_PLAY_SAMPLES: int
DEFAULT_PLAY_QUEUE_MS: int
DEFAULT_COALESCE_MS: int
PREBUFFER_MS: int
STALL_WINDOW_MS: int
STALL_RATIO: float
STALL_SAMPLE_MS: int
RECOVER_GRACE_MS: int
RECOVER_SETTLE_MS: int
WRITE_WAIT_MS: int

class WinPCMOutput(PCMOutput):
    device_name: Incomplete
    samples: Incomplete
    queue_ms: Incomplete
    poll_ms: Incomplete
    coalesce_ms: Incomplete
    recycles: int
    lost_bytes: int
    requeued_bytes: int
    def __init__(self, fmt, *, device=None, samples=..., queue_ms=..., poll_ms: int = 2, coalesce_ms=..., prebuffer_ms=None, session=None) -> None: ...
    def queued_size(self): ...
    def is_active(self): ...
    def clear(self) -> None: ...
    @property
    def buffer_frames(self): ...
    def device_frames(self): ...
    def write_now(self, buf, *, start: bool = True): ...
    def start(self): ...
    def service(self): ...

class WinPCMInput(PCMInput):
    device_name: Incomplete
    samples: Incomplete
    queue_ms: Incomplete
    poll_ms: Incomplete
    def __init__(self, fmt, *, device=None, samples: int = 512, queue_ms: int = 500, poll_ms: int = 2, session=None) -> None: ...
    def queued_size(self): ...

def pcm_out(format=None, *, device=None, latency=None, samples=None, queue_ms=None, coalesce_ms=None, prebuffer_ms=None, poll_ms: int = 2): ...
def pcm_in(format=None, *, device=None, latency=None, samples=None, queue_ms=None, poll_ms: int = 2): ...
