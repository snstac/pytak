"""Tests for the protobuf -> CoT XML reconstruction.

Regression: ``<status battery>`` and ``<precisionlocation>`` are strongly typed
in the TAK protobuf, so they vanish unless _takmsg2xml() rebuilds them. Battery
is the only device-health field an EUD reports, and every protobuf transport
(ws://, wss://, and therefore tak:// enrollment) goes through this path.
"""

import xml.etree.ElementTree as ET

import pytest

from pytak.classes import _takmsg2xml

takproto = pytest.importorskip("takproto")
from takproto.functions import xml2message  # noqa: E402


EUD_XML = b"""<event version='2.0' uid='aa0b0312' type='a-f-G-E-V-C'
 time='2020-02-08T18:10:44.000Z' start='2020-02-08T18:10:44.000Z'
 stale='2020-02-08T18:11:11.000Z' how='h-e'>
<point lat='43.97957317' lon='-66.07737696' hae='26.767999' ce='9999999.0' le='9999999.0'/>
<detail>
<contact callsign='Eliopoli HQ' endpoint='192.168.1.10:4242:tcp'/>
<__group name='Yellow' role='HQ'/>
<status battery='87'/>
<takv platform='WinTAK-CIV' device='LENOVO' os='Windows 10' version='1.10.0.137'/>
<precisionlocation geopointsrc='GPS' altsrc='GPS'/>
</detail></event>"""


def _roundtrip(xml: bytes) -> ET.Element:
    msg = xml2message(xml)
    out = _takmsg2xml(msg)
    assert out is not None
    return ET.fromstring(out)


def test_battery_survives_roundtrip():
    event = _roundtrip(EUD_XML)
    status = event.find("./detail/status")
    assert status is not None, "<status battery> was dropped in protobuf->XML"
    assert status.get("battery") == "87"


def test_precisionlocation_survives_roundtrip():
    event = _roundtrip(EUD_XML)
    prec = event.find("./detail/precisionlocation")
    assert prec is not None
    assert prec.get("geopointsrc") == "GPS"
    assert prec.get("altsrc") == "GPS"


def test_existing_fields_still_present():
    """The added elements must not disturb what already worked."""
    event = _roundtrip(EUD_XML)
    assert event.get("uid") == "aa0b0312"
    assert event.find("./detail/contact").get("callsign") == "Eliopoli HQ"
    assert event.find("./detail/__group").get("name") == "Yellow"
    assert event.find("./detail/takv").get("platform") == "WinTAK-CIV"
    assert event.find("point") is not None


def test_absent_battery_emits_no_status():
    """battery=0 is protobuf's unset default, not a flat battery."""
    no_batt = EUD_XML.replace(b"<status battery='87'/>", b"")
    event = _roundtrip(no_batt)
    assert event.find("./detail/status") is None
