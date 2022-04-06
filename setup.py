#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Setup for the Python Team Awareness Kit (PyTAK) Module.

:author: Greg Albrecht W2GMD <oss@undef.net>
:copyright: Copyright 2022 Greg Albrecht
:license: Apache License, Version 2.0
:source: <https://github.com/ampledata/pytak>
"""

import os
import sys

import setuptools

__title__ = "pytak"
__version__ = "4.0.0"
__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2022 Greg Albrecht"
__license__ = "Apache License, Version 2.0"


def publish():
    """Function for publishing package to pypi."""
    if sys.argv[-1] == "publish":
        os.system("python setup.py sdist")
        os.system("twine upload dist/*")
        sys.exit()


publish()


def read_readme(readme_file="README.rst") -> str:
    """Read the contents of the README file for use as a long_description."""
    readme: str = ""
    this_directory = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(this_directory, readme_file), encoding="UTF-8") as rmf:
        readme = rmf.read()
    return readme


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
    license="Apache License, Version 2.0",
    long_description=read_readme(),
    long_description_content_type="text/x-rst",
    zip_safe=False,
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python",
        "License :: OSI Approved :: Apache Software License"
    ],
    keywords=[
        "Cursor on Target", "ATAK", "TAK", "CoT"
    ]
)
