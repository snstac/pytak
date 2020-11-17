#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Setup for the Python Team Awareness Kit (PyTAK) Module.

:author: Greg Albrecht W2GMD <oss@undef.net>
:copyright: Copyright 2020 Orion Labs, Inc.
:license: Apache License, Version 2.0
:source: <https://github.com/ampledata/pytak>
"""

import os
import setuptools
import sys

__title__ = "pytak"
__version__ = "3.1.1"
__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2020 Orion Labs, Inc."
__license__ = "Apache License, Version 2.0"


def publish():
    """Function for publishing package to pypi."""
    if sys.argv[-1] == "publish":
        os.system("python setup.py sdist")
        os.system("twine upload dist/*")
        sys.exit()


publish()


setuptools.setup(
    version=__version__,
    name=__title__,
    packages=[__title__],
    package_dir={__title__: __title__},
    url=f"https://github.com/ampledata/{__title__}",
    description="Python Team Awareness Kit (PyTAK) Module",
    author="Greg Albrecht",
    author_email="oss@undef.net",
    package_data={"": ["LICENSE"]},
    license=open("LICENSE").read(),
    long_description=open("README.rst").read(),
    zip_safe=False,
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python",
        "License :: OSI Approved :: Apache Software License"
    ],
    keywords=[
        "Cursor on Target", "ATAK", "TAK", "CoT"
    ],
    install_requires=[
        "asyncio_dgram",
        "pycot"
    ]
)
