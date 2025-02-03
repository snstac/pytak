#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# commands.py from https://github.com/snstac/pytak
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""PyTAK Command Line."""

import pytak


def main() -> None:
    """Boilerplate main function."""
    # PyTAK CLI tool boilerplate:
    pytak.cli(__name__.split(".", maxsplit=1)[0])


if __name__ == "__main__":
    main()
