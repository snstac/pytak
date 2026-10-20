#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

"""Regression test: ``import pytak`` must work without ``cryptography`` (#97)."""

import subprocess
import sys

BLOCK_CRYPTOGRAPHY = """
import sys
sys.modules["cryptography"] = None  # makes any `import cryptography...` fail
import pytak
import pytak.crypto_functions as cf
assert cf.USE_CRYPTOGRAPHY is False
print("import-ok")
"""


def test_import_pytak_without_cryptography():
    """Annotations naming cryptography types must not be evaluated at import."""
    result = subprocess.run(
        [sys.executable, "-c", BLOCK_CRYPTOGRAPHY],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "import-ok" in result.stdout
