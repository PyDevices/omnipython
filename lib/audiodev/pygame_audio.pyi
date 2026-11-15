# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from _typeshed import Incomplete
from audiodev import AudioFormat as AudioFormat, PCMInput as PCMInput, PCMOutput as PCMOutput, check_latency as check_latency

DEFAULT_PLAY_SAMPLES: int
DEFAULT_PLAY_QUEUE_MS: int
DEFAULT_COALESCE_MS: int
PREBUFFER_MS: int
STALL_WINDOW_MS: int
STALL_RATIO: float
STALL_SAMPLE_MS: int
RECOVER_GRACE_MS: int
RECOVER_SETTLE_MS: int

class PygamePCMOutput(PCMOutput):
    samples: Incomplete
    poll_ms: Incomplete
    coalesce_ms: Incomplete
    device: int
    channel: Incomplete
    mode: str
    recycles: int
    lost_bytes: int
    requeued_bytes: int
    def __init__(self, fmt, *, samples=..., poll_ms: int = 2, queue_ms=..., coalesce_ms=...) -> None: ...
    def queued_size(self): ...
    def is_active(self): ...
    def service(self) -> None: ...
    def drain(self, timeout_ms=None): ...
    async def adrain(self, timeout_ms=None): ...
    def clear(self) -> None: ...

class PygamePCMInput(PCMInput):
    device_name: Incomplete
    samples: Incomplete
    poll_ms: Incomplete
    def __init__(self, fmt, *, device=None, samples: int = 512, poll_ms: int = 2, queue_ms: int = 500) -> None: ...

def pcm_out(format=None, *, latency=None, samples=None, poll_ms: int = 2, queue_ms=None, coalesce_ms=None): ...
def pcm_in(format=None, *, device=None, latency=None, samples=None, poll_ms: int = 2, queue_ms=None): ...
