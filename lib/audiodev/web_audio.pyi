# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from _typeshed import Incomplete
from audiodev import AudioFormat as AudioFormat, PCMInput as PCMInput, PCMOutput as PCMOutput, check_latency as check_latency
from audiodev.bytequeue import ByteQueue as ByteQueue

class WebPCMOutput(PCMOutput):
    poll_ms: Incomplete
    def __init__(self, fmt, *, poll_ms: int = 4) -> None: ...

class WebPCMInput(PCMInput):
    poll_ms: Incomplete
    samples: Incomplete
    def __init__(self, fmt, *, poll_ms: int = 4, queue_ms: int = 500, samples: int = 2048) -> None: ...

def pcm_out(format=None, *, latency=None, poll_ms: int = 4): ...
def pcm_in(format=None, *, latency=None, poll_ms: int = 4, queue_ms: int = 500, samples=None): ...
