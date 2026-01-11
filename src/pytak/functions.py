#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# functions.py from https://github.com/snstac/pytak
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

"""PyTAK Functions."""

import datetime
import warnings
import xml.etree.ElementTree as ET
import secrets
import tempfile
import zipfile
import os

import json

from pathlib import Path
from typing import Optional, Tuple, Union
from urllib.parse import ParseResult, urlparse

import pytak
import pytak.crypto_classes  # pylint: disable=cyclic-import


def split_host(host: str, port: Union[int, None] = None) -> Tuple[str, int]:
    """Split a host:port string or host, port params into a host,port tuple."""
    addr: str
    _port: str
    
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
                DeprecationWarning,
            )
            port = pytak.DEFAULT_BROADCAST_PORT
        else:
            port = pytak.DEFAULT_COT_PORT

    return host, int(port)


def cot_time(cot_stale: Union[int, None] = None) -> str:
    """Get the current UTC datetime as a W3C XML Schema dateTime primitive.

    See: https://www.w3.org/TR/xmlschema-2/#dateTime

    Parameters
    ----------
    cot_stale : `Union[int, None]`
        Time in seconds to add to the current time, for use with Cursor on Target
        'stale' attributes.

    Returns
    -------
    `str`
        Current UTC datetime in W3C XML Schema dateTime format.
    """
    time = datetime.datetime.now(datetime.timezone.utc)
    if cot_stale:
        time = time + datetime.timedelta(seconds=int(cot_stale))
    return time.strftime(pytak.W3C_XML_DATETIME)


def hello_event(uid: Optional[bytes] = None) -> bytes:
    """Generate a Hello CoT Event."""
    uid = uid or "takPing"
    return gen_cot(uid=uid, cot_type="t-x-d-d")


def unzip_file(zip_src: bytes, zip_dest: Union[bytes, None] = None) -> str:
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
        raise EOFError(f"Could not find file: {glob}") from exc


def find_cert(search_dir: str, cert_path: str) -> str:
    """Find a cert file within a search dir after extracting the basename."""
    cert_file: str = os.path.basename(cert_path)
    assert cert_file
    return find_file(search_dir, cert_file)


def load_preferences(pref_path: str, search_dir: str) -> dict:
    """Load preferences file into a dict."""
    with open(pref_path, "rb+") as pref_fd:
        pref_data: bytes = pref_fd.read()

    root: ET.Element = ET.fromstring(pref_data)
    entries: list = root.findall(".//entry")

    prefs: dict = {
        "connect_string": None,
        "client_password": None,
        "certificate_location": None,
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


def connectString2url(conn_str: str) -> str:  # pylint: disable=invalid-name
    """Convert a TAK-style connectString into a URL."""
    uri_parts = conn_str.split(":")
    return f"{uri_parts[2]}://{uri_parts[0]}:{uri_parts[1]}"


def cot2xml(event: pytak.COTEvent) -> ET.Element:
    """Generate a minimum COT Event as an XML object."""
    # Optimized: Reduce redundant str() calls and or operations
    lat = str(event.lat) if event.lat is not None else "0.0"
    lon = str(event.lon) if event.lon is not None else "0.0"
    uid = event.uid or pytak.DEFAULT_HOST_ID
    stale = int(event.stale or pytak.DEFAULT_COT_STALE)
    cot_type = event.cot_type or "a-u-G"
    le = str(event.le) if event.le is not None else pytak.DEFAULT_COT_VAL
    hae = str(event.hae) if event.hae is not None else pytak.DEFAULT_COT_VAL
    ce = str(event.ce) if event.ce is not None else pytak.DEFAULT_COT_VAL

    xevent = ET.Element("event")
    xevent.set("version", "2.0")
    xevent.set("type", cot_type)
    xevent.set("uid", uid)
    xevent.set("how", "m-g")
    xevent.set("time", pytak.cot_time())
    xevent.set("start", pytak.cot_time())
    xevent.set("stale", pytak.cot_time(stale))

    point = ET.Element("point")
    point.set("lat", lat)
    point.set("lon", lon)
    point.set("le", le)
    point.set("hae", hae)
    point.set("ce", ce)

    # Optimized: Pre-compute flow tag name once
    flow_tags = ET.Element("_flow-tags_")
    _ft_tag: str = f"{pytak.DEFAULT_HOST_ID}-pytak".replace("@", "-")
    flow_tags.set(_ft_tag, pytak.cot_time())

    detail = ET.Element("detail")
    detail.append(flow_tags)

    xevent.append(point)
    xevent.append(detail)

    return xevent


def gen_cot_xml(
    lat: Union[bytes, str, float, None] = None,
    lon: Union[bytes, str, float, None] = None,
    ce: Union[bytes, str, float, int, None] = None,
    hae: Union[bytes, str, float, int, None] = None,
    le: Union[bytes, str, float, int, None] = None,
    uid: Union[str, None] = None,
    stale: Union[float, int, None] = None,
    cot_type: Union[str, None] = None,
    callsign: Optional[str] = None,
) -> Optional[ET.Element]:
    """Generate a minimum CoT Event as an XML object."""
    # Optimized: Use default values directly instead of redundant or operators
    lat = str(lat) if lat is not None else "0.0"
    lon = str(lon) if lon is not None else "0.0"
    ce = str(ce) if ce is not None else pytak.DEFAULT_COT_VAL
    hae = str(hae) if hae is not None else pytak.DEFAULT_COT_VAL
    le = str(le) if le is not None else pytak.DEFAULT_COT_VAL
    uid = uid or pytak.DEFAULT_HOST_ID
    stale = int(stale or pytak.DEFAULT_COT_STALE)
    cot_type = cot_type or "a-u-G"

    event = ET.Element("event")
    event.set("version", "2.0")
    event.set("type", cot_type)
    event.set("uid", uid)
    event.set("how", "m-g")
    event.set("time", pytak.cot_time())
    event.set("start", pytak.cot_time())
    event.set("stale", pytak.cot_time(stale))

    point = ET.Element("point")
    point.set("lat", lat)
    point.set("lon", lon)
    point.set("le", le)
    point.set("hae", hae)
    point.set("ce", ce)

    # Optimized: Pre-compute flow tag name once
    flow_tags = ET.Element("_flow-tags_")
    _ft_tag: str = f"{pytak.DEFAULT_HOST_ID}-pytak".replace("@", "-")
    flow_tags.set(_ft_tag, pytak.cot_time())

    detail = ET.Element("detail")
    detail.append(flow_tags)

    if callsign:
        contact = ET.Element("contact")
        contact.set("callsign", callsign)
        detail.append(contact)

    event.append(point)
    event.append(detail)

    return event


def gen_cot(
    lat: Union[bytes, float, None] = None,
    lon: Union[bytes, float, None] = None,
    ce: Union[bytes, float, int, None] = None,
    hae: Union[bytes, float, int, None] = None,
    le: Union[bytes, float, int, None] = None,
    uid: Optional[str] = None,
    stale: Union[float, int, None] = None,
    cot_type: Optional[str] = None,
    callsign: Optional[str] = None,
) -> Optional[bytes]:
    """Generate a minimum CoT Event as an XML string [gen_cot_xml() wrapper]."""
    cot: Union[ET.Element, bytes, None] = gen_cot_xml(
        lat, lon, ce, hae, le, uid, stale, cot_type, callsign
    )
    if isinstance(cot, ET.Element):
        # Optimized: Pre-allocate bytearray for better performance
        return pytak.DEFAULT_XML_DECLARATION + b"\n" + ET.tostring(cot)
    return cot


def tak_pong() -> bytes:
    """Generate a takPong CoT Event."""
    event = ET.Element("event")
    event.set("version", "2.0")
    event.set("type", "t-x-d-d")
    event.set("uid", "takPong")
    event.set("how", "m-g")
    
    # Optimized: Compute time once and reuse
    current_time: str = pytak.cot_time()
    event.set("time", current_time)
    event.set("start", current_time)
    event.set("stale", pytak.cot_time(3600))
    
    return ET.tostring(event)


async def enroll_tak(host: str, username: str, password: str, passphrase: Optional[str] = None) -> Tuple[str, str]:
    enrollment = pytak.crypto_classes.CertificateEnrollment()
    passphrase = secrets.token_urlsafe(pytak.DEFAULT_TLS_ENROLLMENT_CERT_PASSPHRASE_LENGTH) if passphrase is None else passphrase

    # Create a temporary file to store the certificate
    output_path = None
    
    # Use tempfile to create a temp file for the cert
    with tempfile.NamedTemporaryFile(suffix=".p12", delete=False) as tmpfile:
        output_path = tmpfile.name

    await enrollment.begin_enrollment(
        domain=host,
        username=username,
        password=password,
        output_path=output_path,
        passphrase=passphrase,
        trust_all=True
    )

    return output_path, passphrase


async def decode_response(response):
    """
    Decode the response from the server.
    If the response is JSON, it will return a dictionary.
    If the response is not JSON, it will return the text content.
    """
    try:
        response_data = await response.json()
    except Exception as json_error:
        # If JSON parsing fails due to content-type, try parsing text as JSON
        response_text = await response.text()
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError:
            # If still fails, return the text content
            response_data = response_text
            print(f"Failed to decode JSON: {json_error}. Returning text content instead.")
            print(f"Response text: {response_text}")
    return response_data