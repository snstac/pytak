#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2023 Greg Albrecht <oss@undef.net>
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
# Author:: Greg Albrecht W2GMD <oss@undef.net>
#

"""PyTAK Functions."""

import datetime
import warnings
import xml.etree.ElementTree as ET
import tempfile
import zipfile
import os

from pathlib import Path
from typing import Tuple, Union
from urllib.parse import ParseResult, urlparse

import pytak  # pylint: disable=cyclic-import

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2023 Greg Albrecht"
__license__ = "Apache License, Version 2.0"


def split_host(host: str, port: Union[int, None] = None) -> Tuple[str, int]:
    """Split a host:port string or host, port params into a host,port tuple."""
    if ":" in host:
        addr, _port = host.split(":")
        port = int(_port)
    elif port:
        addr = host
        port = int(port)
    else:
        addr = host
        port = int(pytak.DEFAULT_COT_PORT)
    return addr, int(port)


def parse_url(url: Union[str, ParseResult]) -> Tuple[str, int]:
    """Parse a CoT destination URL."""
    if isinstance(url, str):
        _url: ParseResult = urlparse(url)
    elif isinstance(url, ParseResult):
        _url = url

    assert isinstance(_url, ParseResult)

    port: Union[int, str] = pytak.DEFAULT_BROADCAST_PORT
    host: str = _url.netloc

    if ":" in _url.netloc:
        host, port = _url.netloc.split(":")
    else:
        if "broadcast" in _url.scheme:
            port = pytak.DEFAULT_BROADCAST_PORT
        elif "multicast" in _url.scheme:
            warnings.warn(
                "You no longer need to specify '+multicast' in the COT_URL.",
                DeprecationWarning
            )
            port = pytak.DEFAULT_BROADCAST_PORT
        else:
            port = pytak.DEFAULT_COT_PORT

    return host, int(port)


def cot_time(cot_stale: Union[int, None] = None) -> str:
    """Get the current UTC datetime in ISO-8601 format.

    Parameters
    ----------
    cot_stale : `Union[int, None]`
        Time in seconds to add to the current time, for use with Cursor on Target
        'stale' attributes.

    Returns
    -------
    `str`
        Current UTC datetime in ISO-8601 format.
    """
    time = datetime.datetime.now(datetime.timezone.utc)
    if cot_stale:
        time = time + datetime.timedelta(seconds=int(cot_stale))
    return time.strftime(pytak.ISO_8601_UTC)


def hello_event(uid: Union[str, None] = None) -> bytes:
    """Generate a Hello CoT Event."""
    uid = uid or pytak.DEFAULT_HOST_ID

    root = ET.Element("event")
    root.set("version", "2.0")
    root.set("type", "t-x-d-d")
    root.set("uid", uid)
    root.set("how", "m-g")
    root.set("time", cot_time())
    root.set("start", cot_time())
    root.set("stale", cot_time(3600))

    return ET.tostring(root)


def unzip_file(zip_src: str, zip_dest: Union[str, None] = None) -> str:
    """Unzips a given zip file, returning the destination path."""
    _zip_dest: str = zip_dest or tempfile.mkdtemp(prefix="pytak_dp_")
    with zipfile.ZipFile(zip_src, "r") as zip_ref:
        zip_ref.extractall(_zip_dest)
    assert os.path.exists(_zip_dest)
    return _zip_dest


def find_file(search_dir: str, glob: str) -> str:
    """Find the first file for a given glob in the search directory."""
    try:
        files = list(Path(search_dir).rglob(glob))
        assert len(files) > 0
        return str(files[0])
    except Exception as exc:
        raise Exception(f"Could not find file: {glob}") from exc


def find_cert(search_dir: str, cert_path: str) -> str:
    """Find a cert file within a search dir after extracting the basename."""
    cert_file: str = os.path.basename(cert_path)
    assert cert_file
    return find_file(search_dir, cert_file)


def load_preferences(pref_path: str, search_dir: str):
    """Load preferences file into a dict."""
    with open(pref_path, "rb+") as pref_fd:
        pref_data = pref_fd.read()

    root = ET.fromstring(pref_data)
    entries = root.findall(".//entry")

    prefs = {
        "connect_string": None,
        "client_password": None,
        "certificate_location": None
    }

    # Determine the COT URL, client certificate and password
    for entry in entries:
        if entry.attrib["key"] == "connectString0":
            prefs["connect_string"] = entry.text
        if entry.attrib["key"] == "clientPassword":
            prefs["client_password"] = entry.text
        if entry.attrib["key"] == "certificateLocation":
            prefs["certificate_location"] = find_cert(search_dir, entry.text)

    return prefs


def cs2url(conn_str: str) -> str:
    """Convert a TAK-style connectString into a URL."""
    uri_parts = conn_str.split(":")
    return f"{uri_parts[2]}://{uri_parts[0]}:{uri_parts[1]}"


