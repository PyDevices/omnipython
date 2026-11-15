# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from audiodev import ToneOutput as ToneOutput

class PWMToneOutput(ToneOutput):
    def __init__(self, pwm, *, session=None, power=None) -> None: ...
    @property
    def pwm(self): ...

def tone_out(pwm, *, session=None, power=None): ...
