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
import tempfile
import zipfile
import os
import uuid

from pathlib import Path
from typing import Optional, Tuple, Union
from urllib.parse import ParseResult, urlparse

import pytak  # pylint: disable=cyclic-import


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

def is_valid_datetime(datetime_str: str) -> bool:
    """
    This validates if the datetime is in the right format
    Makes both checks with millis and without millis, either or still should be good

    Parameters
    ----------
    datetime_str : `str`
        Datetime as string that needs to be validated according to the defined format

    Returns
    -------
    `bool`
        True if format is good, otherwise False
    """
    try:
        # Try to parse with milliseconds
        datetime.datetime.strptime(datetime_str, pytak.W3C_XML_DATETIME)
        return True
    except ValueError:
        # If parsing with milliseconds fails, try parsing without milliseconds
        try:
            datetime.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ")
            return True
        except ValueError:
            # If both formats fail, return False
            warnings.warn(f"Datetime [{datetime_str}] format is wrong, must be [%Y-%m-%dT%H:%M:%S.%fZ] or [%Y-%m-%dT%H:%M:%SZ]. Defaulting to pytak.cot_time()")
            return False
    except Exception as e:
        warnings.warn(f"{e}\nSome exception happened when parsing datetime. Defaulting to pytak.cot_time()")
        return False


def hello_event(uid: Optional[bytes] = None) -> bytes:
    """Generate a Hello CoT Event."""
    uid = uid or "takPing"
    return gen_cot(uid=uid, cot_type="t-x-d-d")


def unzip_file(zip_src: bytes, zip_dest: Union[bytes, None] = None) -> bytes:
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


def load_preferences(pref_path: str, search_dir: str):
    """Load preferences file into a dict."""
    with open(pref_path, "rb+") as pref_fd:
        pref_data = pref_fd.read()

    root = ET.fromstring(pref_data)
    entries = root.findall(".//entry")

    prefs = {
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
    lat = str(event.lat or "0.0")
    lon = str(event.lon or "0.0")
    uid = event.uid or pytak.DEFAULT_HOST_ID
    stale = int(event.stale or pytak.DEFAULT_COT_STALE)
    cot_type = event.cot_type or "a-u-G"
    le = str(event.le or pytak.DEFAULT_COT_VAL)
    hae = str(event.hae or pytak.DEFAULT_COT_VAL)
    ce = str(event.ce or pytak.DEFAULT_COT_VAL)

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

    flow_tags = ET.Element("_flow-tags_")
    _ft_tag: str = f"{pytak.DEFAULT_HOST_ID}-pytak".replace("@", "-")
    flow_tags.set(_ft_tag, pytak.cot_time())

    detail = ET.Element("detail")
    detail.append(flow_tags)

    xevent.append(point)
    xevent.append(detail)

    return xevent

# better to not type hint any of the arguments as bytes
def gen_cot_xml(
    lat: Union[str, float, None] = None,
    lon: Union[str, float, None] = None,
    ce: Union[str, float, int, None] = None,
    hae: Union[str, float, int, None] = None,
    le: Union[str, float, int, None] = None,
    uid: Union[str, None] = None,
    stale: Union[float, int, None] = None,
    cot_type: Union[str, None] = None,
) -> Optional[ET.Element]:
    """Generate a minimum CoT Event as an XML object

    Parameters
    ----------
    lat : `str` or `float` or `None`
        latitude for point in COT

    lon : `str` or `float` or `None`
        longitude for point in COT

    ce : `str` or `float` or `int` or `None`
        circular error around point in meters. Can be default value `9999999.0`

    hae : `str` or `float` or `int` or `None`
        height above ellipsoid in meters. Can be default value `9999999.0`
    
    le : `str` or `float` or `int` or `None`
        linear error above point in meters. Can be default value `9999999.0`

    uid : `str` or `None`
        uid string for COT. Different COT events with the same uid, will replace each other with the latest updating the older. Different COT events with different `uid` can be present in TAK at the same time

    stale : `float` or `int` or `None`
        interval in seconds that defines the ending of an event. A marker will grey out after this interval has passed from the start time. 

    cot_type : `str` or `None`
        COT type string defined in MIL-STD-2525

    Returns
    -------
    `ET.Element`
        COT event as XML Element object

    Notes
    -----
    Flow tags will be appended automatically
    """

    lat = str(lat or "0.0")
    lon = str(lon or "0.0")
    ce = str(ce or pytak.DEFAULT_COT_VAL)
    hae = str(hae or pytak.DEFAULT_COT_VAL)
    le = str(le or pytak.DEFAULT_COT_VAL)
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

    flow_tags = ET.Element("_flow-tags_")
    # FIXME: Add PyTAK version to the flow tags.
    _ft_tag: str = f"{pytak.DEFAULT_HOST_ID}-pytak".replace("@", "-")
    flow_tags.set(_ft_tag, pytak.cot_time())

    detail = ET.Element("detail")
    detail.append(flow_tags)

    event.append(point)
    event.append(detail)

    return event


def gen_cot_detailed_xml(
    lat: Union[str, float, None] = None,
    lon: Union[str, float, None] = None,
    hae: Union[str, float, int, None] = None,
    ce: Union[str, float, int, None] = None,
    le: Union[str, float, int, None] = None,
    uid: Union[str, None] = None,
    stale: Union[float, int, None] = None,
    cot_type: Union[str, None] = None,
    cot_how: Union[str, None] = None,
    timestamp: Union[str, None] = None,
    access: Union[pytak.MIL_STD_6090_ACCESS_VALUES, str, None] = None,
    caveat: Union[str, None] = None,
    releasableto: Union[str, None] = None,
    qos: Union[str, None] = None,
    opex: Union[str, None] = None,
    callsign: Union[str, None] = None,
    remarks: Union[str, None] = None,
    flow_tags_include: Union[bool, None] = False,
    flow_tags_custom: Union[str, None] = None,
) -> Optional[ET.Element]:
    """Generate a more detailed CoT Event as an XML object.

    Parameters
    ----------
    lat : `str` or `float` or `None`
        latitude for point in COT

    lon : `str` or `float` or `None`
        longitude for point in COT

    ce : `str` or `float` or `int` or `None`
        circular error around point in meters. Can be default value `9999999.0`

    hae : `str` or `float` or `int` or `None`
        height above ellipsoid in meters. Can be default value `9999999.0`
    
    le : `str` or `float` or `int` or `None`
        linear error above point in meters. Can be default value `9999999.0`

    uid : `str` or `None`
        uid string for COT. Different COT events with the same uid, will replace each other with the latest updating the older. Different COT events with different `uid` can be present in TAK at the same time

    stale : `float` or `int` or `None`
        interval in seconds that defines the ending of an event. A marker will grey out after this interval has passed from the start time. 

    cot_type : `str` or `None`
        COT type string defined in MIL-STD-2525

    cot_how : `str` or `None`
        how the COT was generated as defined in MIL-STD-2525

    timestamp : `str` or `None`
        time stamp that is placed on the event when it was generated

    access : `str` or `None`
        access type for COT as defined in MIL-STD-6090

    caveat : `str` or `None`
        safeguarding and dissemination of information as defined in MIL-STD-6090

    releasableto : `str` or `None`
        indicates which countries/country can have the information releasable. Refer to DFI 4127/701 for a list of 3-digit country codes

    qos : `str`or `None`
        quality of service to how to treat events

    opex : `str` or `None`
        indicates if the event is part of live operation, exercise, or simulation

    callsign : `str` or `None`
        callsign for marker that will appear as its label. When callsign is missing, `uid` becomes the label for the marker
    
    remarks : `str` or None
        user defined remarks that will be appended to `detail` element. These can be used to provide more information about a marker
    
    flow_tags_include : `bool` or `None`
        flag to indicate if flow tags are to be included or no. TAK server includes them by default. Here default is False
    
    flow_tags_custom: `str` or `None`
        user provided flow tags as string
    
    Returns
    -------
    `ET.Element`
        COT event as XML Element object
    
        Notes
    -----
    User can provide the custom flow tag string, but it will be included only if the `flow_tags_include` flag is set to `True`
    """

    lat = str(lat or "0.0")
    lon = str(lon or "0.0")
    hae = str(hae or pytak.DEFAULT_COT_VAL)
    ce = str(ce or pytak.DEFAULT_COT_VAL)
    le = str(le or pytak.DEFAULT_COT_VAL)
    uid = uid or f"{pytak.DEFAULT_HOST_ID}_{uuid.uuid4()}"
    time = timestamp if pytak.is_valid_datetime(timestamp) else pytak.cot_time()
    stale = int(stale or pytak.DEFAULT_COT_STALE)
    cot_type = cot_type or "a-u-G"
    cot_how = cot_how or "m-g"

    event = ET.Element("event")
    event.set("version", "2.0")
    event.set("type", cot_type)
    event.set("uid", uid)
    event.set("how", cot_how)
    event.set("time", time)
    event.set("start", pytak.cot_time())
    event.set("stale", pytak.cot_time(stale))

    if access:
        try:
            pytak.MIL_STD_6090_ACCESS_VALUES(access)
            event.set("access", str(access.value))
        except ValueError:
            event.set("access", str(pytak.MIL_STD_6090_ACCESS_VALUES.UNDEFINED.value))

    if caveat:
        event.set("caveat", str(caveat))
    if releasableto:
        event.set("releasableto", str(releasableto))
    if qos:
        event.set("qos", str(qos))
    if opex:
        event.set("opex", str(opex))

    point = ET.Element("point")
    point.set("lat", lat)
    point.set("lon", lon)
    point.set("hae", hae)
    point.set("le", le)
    point.set("ce", ce)

    event.append(point)

    detail = ET.Element("detail")

    # Add callsign
    if callsign:
        ET.SubElement(detail, "contact", {"callsign": callsign})

    # Add remarks
    if remarks:
        remark = ET.Element("remarks")
        text: str = remarks
        remark.text = text
        detail.append(remark)

    # Add flow tags
    if flow_tags_include:
        flow_tags = ET.Element("_flow-tags_")
        if flow_tags_custom:
            _ft_tag: str = flow_tags_custom
        else:
            # FIXME: Add PyTAK version to the flow tags.
            _ft_tag: str = f"{pytak.DEFAULT_HOST_ID}-pytak".replace("@", "-")

        flow_tags.set(_ft_tag, pytak.cot_time())
        detail.append(flow_tags)

    # if nothing appends to the `detail` element, that is fine
    # will be just a closed tag: `<detail />`
    event.append(detail)

    return event


def gen_cot(
    lat: Union[str, float, None] = None,
    lon: Union[str, float, None] = None,
    ce: Union[str, float, int, None] = None,
    hae: Union[str, float, int, None] = None,
    le: Union[str, float, int, None] = None,
    uid: Optional[str] = None,
    stale: Union[float, int, None] = None,
    cot_type: Optional[str] = None,
) -> Optional[bytes]:
    """Generate a minimum CoT Event as an XML string [gen_cot_xml() wrapper]."""
    cot: Union[ET.Element, bytes, None] = gen_cot_xml(
        lat, lon, ce, hae, le, uid, stale, cot_type
    )
    if isinstance(cot, ET.Element):
        # FIXME: This is a hack to add the XML declaration to the CoT event.
        #       When Python 3.7 is EOL'd, we can use 3.8's 'xml_declaration' kwarg.
        cot = b"\n".join([pytak.DEFAULT_XML_DECLARATION, ET.tostring(cot)])
    return cot


def tak_pong():
    """Generate a takPong CoT Event."""
    event = ET.Element("event")
    event.set("version", "2.0")
    event.set("type", "t-x-d-d")
    event.set("uid", "takPong")
    event.set("how", "m-g")
    event.set("time", pytak.cot_time())
    event.set("start", pytak.cot_time())
    event.set("stale", pytak.cot_time(3600))
    return ET.tostring(event)


def gen_delete_cot_xml(cot_uid_to_delete: str, flow_tags_include: Union[bool, None] = False, flow_tags_custom: Union[str, None] = None) -> bytes:
    """Function to generate a COT event that can delete any previously sent COT that matches the `uid`

    Parameters
    ----------
    uid : `str`
        uid of COT to be deleted
    
    flow_tags_include : `bool` or `None`
        flag to indicate if flow tags are to be included or no. TAK server includes them by default. Here default is False
    
    flow_tags_custom: `str` or `None`
        user provided flow tags as string

    Returns
    -------
    `bytes`
        COT event in bytes

    Notes
    -----
    User can provide the custom flow tag string, but it will be included only if the `flow_tags_include` flag is set to `True`
    """

    event = ET.Element("event")
    event.set("version", "2.0")
    # this could be either a unique id or the same uid as the one to delete
    event.set("uid", str(uuid.uuid4()))  
    event.set("how", "m-g")
    event.set("type", pytak.DEFAULT_COT_DELETE_TYPE)  # to delete
    event.set("time", pytak.cot_time())
    event.set("start", pytak.cot_time())
    event.set("stale", pytak.cot_time(1)) # stale does not matter either

    # point location does not matter, but is needed for a valid COT event xml
    pt_attr = {
        "lat": "0.0",
        "lon": "0.0",
        "hae": "0.0",
        "ce": pytak.DEFAULT_COT_VAL,
        "le": pytak.DEFAULT_COT_VAL,
    }

    ET.SubElement(event, "point", attrib=pt_attr)

    detail = ET.Element("detail")
    # this is the important part
    ET.SubElement(detail, "link", {"uid": str(cot_uid_to_delete), "relation": "none", "type": "none"})
    ET.SubElement(detail, "__forcedelete")


    # Add flow tags
    if flow_tags_include:
        flow_tags = ET.Element("_flow-tags_")
        if flow_tags_custom:
            _ft_tag: str = flow_tags_custom
        else:
            # FIXME: Add PyTAK version to the flow tags.
            _ft_tag: str = f"{pytak.DEFAULT_HOST_ID}-pytak".replace("@", "-")

        flow_tags.set(_ft_tag, pytak.cot_time())
        detail.append(flow_tags)

    event.append(detail)

    cot = b"\n".join([pytak.DEFAULT_XML_DECLARATION, ET.tostring(event)])
    return cot