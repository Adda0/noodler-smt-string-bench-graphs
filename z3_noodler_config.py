#!/usr/bin/env python
"""z3-noodler-config.py
"""

import pathlib
import enum

TIMEOUT = 120  # In seconds.
TIMEOUT_VAL = TIMEOUT * 1.1
TIME_MIN = 0.01


class ExtendedEnum(enum.Enum):
    @classmethod
    def values(cls):
        return list(map(lambda c: c.value, cls))

    @classmethod
    def names(cls):
        return list(map(lambda c: c.name, cls))

    @classmethod
    def items(cls):
        return list(map(lambda c: c, cls))


class Benchmark(ExtendedEnum):
    slog = "slog"
    slent = "slent"
    norn = "norn"
    sygus_qgen = "sygus_qgen"
    leetcode = "leetcode"
    kaluza = "kaluza"
    # regex = "regex"


class Tool(ExtendedEnum):
    noodler = "z3-noodler-9f5e602"
    noodler_underapprox = "z3-noodler-9f5e602-underapprox"
    noodler_common = "z3-noodler-common"
    cvc5 = "cvc5"
    z3 = "z3"
    z3_str_re = "z3strRE"
    z3_trau = "z3-trau"
    z3_str_4 = "z3str4"
    ostrich = "ostrich"
