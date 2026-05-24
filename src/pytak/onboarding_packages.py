#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

"""TAK onboarding data packages from enrollment deep-links."""

from __future__ import annotations

import io
import os
import re
import secrets
import uuid
import zipfile
from html import escape as xml_escape
from typing import Any, Dict, Optional

from pytak.client_functions import parse_tak_url
from pytak.constants import (
    DEFAULT_TLS_ENROLLMENT_CERT_PASSPHRASE_LENGTH,
    DEFAULT_TAK_STREAMING_PORT,
)
from pytak.crypto_functions import write_enrollment_artifacts


def _xml_attr_escape(value: str) -> str:
    return xml_escape(value, {'"': "&quot;", "'": "&apos;"})


def build_connection_config_pref_xml(
    *,
    stream_description: str,
    streaming_host: str,
    streaming_port: int,
    use_ssl: bool = True,
    ca_password: str,
    client_password: str,
    location_callsign: str,
    location_team: str = "Red",
    atak_role_type: str = "Team Member",
    package_layout: str = "atak",
) -> str:
    """Body for config.pref (cot_streams + com.atakmap.app_preferences)."""
    proto = "ssl" if use_ssl else "tcp"
    connect = f"{streaming_host}:{streaming_port}:{proto}"
    if package_layout == "itak":
        ca_entry = "caCert.p12"
        client_entry = "clientCert.p12"
    else:
        ca_entry = "cert/caCert.p12"
        client_entry = "cert/clientCert.p12"
    return (
        "<?xml version='1.0' encoding='ASCII' standalone='yes'?>\n"
        "<preferences>\n"
        '  <preference version="1" name="cot_streams">\n'
        '    <entry key="count" class="class java.lang.Integer">1</entry>\n'
        f'    <entry key="description0" class="class java.lang.String">'
        f"{xml_escape(stream_description)}</entry>\n"
        '    <entry key="enabled0" class="class java.lang.Boolean">true</entry>\n'
        f'    <entry key="connectString0" class="class java.lang.String">'
        f"{xml_escape(connect)}</entry>\n"
        f'    <entry key="caLocation0" class="class java.lang.String">'
        f"{xml_escape(ca_entry)}</entry>\n"
        f'    <entry key="caPassword0" class="class java.lang.String">'
        f"{xml_escape(ca_password)}</entry>\n"
        f'    <entry key="clientPassword0" class="class java.lang.String">'
        f"{xml_escape(client_password)}</entry>\n"
        f'    <entry key="certificateLocation0" class="class java.lang.String">'
        f"{xml_escape(client_entry)}</entry>\n"
        "  </preference>\n"
        '  <preference version="1" name="com.atakmap.app_preferences">\n'
        '    <entry key="displayServerConnectionWidget" class="class java.lang.Boolean">true</entry>\n'
        '    <entry key="atakControlForcePortrait" class="class java.lang.Boolean">true</entry>\n'
        f'    <entry key="locationCallsign" class="class java.lang.String">'
        f"{xml_escape(location_callsign)}</entry>\n"
        f'    <entry key="locationTeam" class="class java.lang.String">'
        f"{xml_escape(location_team)}</entry>\n"
        f'    <entry key="atakRoleType" class="class java.lang.String">'
        f"{xml_escape(atak_role_type)}</entry>\n"
        "  </preference>\n"
        "</preferences>\n"
    )


def build_connection_manifest_xml(
    *,
    uid: str,
    display_name: str,
    on_receive_delete: bool = True,
    package_layout: str = "atak",
) -> str:
    """Mission package manifest; zipEntry paths must match ZIP layout."""
    ord_part = ""
    if on_receive_delete:
        ord_part = '\n    <Parameter name="onReceiveDelete" value="true"/>'
    if package_layout == "itak":
        contents = (
            '    <Content ignore="false" zipEntry="config.pref"/>\n'
            '    <Content ignore="false" zipEntry="caCert.p12"/>\n'
            '    <Content ignore="false" zipEntry="clientCert.p12"/>\n'
        )
    else:
        contents = (
            '    <Content ignore="false" zipEntry="certs/config.pref"/>\n'
            '    <Content ignore="false" zipEntry="certs/caCert.p12"/>\n'
            '    <Content ignore="false" zipEntry="certs/clientCert.p12"/>\n'
        )
    return (
        '<MissionPackageManifest version="2">\n'
        "  <Configuration>\n"
        f'    <Parameter name="uid" value="{_xml_attr_escape(uid)}"/>\n'
        f'    <Parameter name="name" value="{_xml_attr_escape(display_name)}"/>'
        f"{ord_part}\n"
        "  </Configuration>\n"
        "  <Contents>\n"
        f"{contents}"
        "  </Contents>\n"
        "</MissionPackageManifest>\n"
    )


def build_connection_data_package_zip(
    *,
    config_pref_xml: str,
    manifest_xml: str,
    client_p12_path: str,
    trust_p12_path: str,
    package_layout: str = "atak",
) -> bytes:
    """Build ATAK-family or iTAK connection ZIP (ZIP_STORED, uncompressed)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:

        def _add_bytes(name: str, data: bytes) -> None:
            zi = zipfile.ZipInfo(name)
            zi.compress_type = zipfile.ZIP_STORED
            zf.writestr(zi, data)

        def _add_file(name: str, path: str) -> None:
            with open(path, "rb") as f:
                _add_bytes(name, f.read())

        _add_bytes("MANIFEST/manifest.xml", manifest_xml.encode("utf-8"))
        if package_layout == "itak":
            _add_bytes("config.pref", config_pref_xml.encode("utf-8"))
            _add_file("caCert.p12", trust_p12_path)
            _add_file("clientCert.p12", client_p12_path)
        else:
            _add_bytes("certs/config.pref", config_pref_xml.encode("utf-8"))
            _add_file("certs/caCert.p12", trust_p12_path)
            _add_file("certs/clientCert.p12", client_p12_path)
    return buf.getvalue()


def sanitize_package_stem(name: str) -> str:
    """Filesystem-safe package folder name."""
    return re.sub(r"[^\w.\-]+", "_", name).strip("._") or "enrollment"


async def enroll_onboarding_package(
    tak_url: str,
    output_dir: str = "data-packages",
    *,
    package_stem: Optional[str] = None,
    streaming_host: Optional[str] = None,
    streaming_port: int = DEFAULT_TAK_STREAMING_PORT,
    stream_description: Optional[str] = None,
    location_callsign: Optional[str] = None,
    location_team: str = "Red",
    atak_role_type: str = "Team Member",
    passphrase: Optional[str] = None,
    on_receive_delete: bool = True,
) -> Dict[str, Any]:
    """
    Enroll via a ``tak://`` URL and write certs plus ATAK/iTAK connection ZIPs.

    Returns a dict of output paths and metadata.
    """
    if not tak_url.strip().lower().startswith("tak://"):
        raise ValueError(f"Expected tak:// enrollment URL, got: {tak_url!r}")

    try:
        from pytak.crypto_classes import CertificateEnrollment
    except ImportError as exc:
        raise ImportError(
            "Onboarding packages require pytak[with-aiohttp,with-crypto]. "
            "Install with: python3 -m pip install pytak[with-aiohttp,with-crypto]"
        ) from exc

    params = parse_tak_url(tak_url)
    hostname = params["hostname"]
    username = params["username"]
    token = params["token"]
    stem = package_stem or sanitize_package_stem(username)
    pkg_root = os.path.abspath(os.path.join(output_dir, stem))
    certs_dir = os.path.join(pkg_root, "certs")
    os.makedirs(certs_dir, exist_ok=True)

    pw = passphrase or secrets.token_urlsafe(
        DEFAULT_TLS_ENROLLMENT_CERT_PASSPHRASE_LENGTH
    )
    enroll_p12 = os.path.join(certs_dir, f"{stem}.p12")

    enrollment = CertificateEnrollment()
    await enrollment.begin_enrollment(
        domain=hostname,
        username=username,
        password=token,
        output_path=enroll_p12,
        passphrase=pw,
        trust_all=True,
    )

    if not os.path.isfile(enroll_p12):
        raise RuntimeError(
            f"TAK certificate enrollment failed for {username}@{hostname}"
        )

    artifacts = write_enrollment_artifacts(enroll_p12, pw, certs_dir, stem)
    trust_p12 = artifacts.get("pkcs12_truststore_path")
    client_p12 = artifacts["pkcs12_path"]
    if not trust_p12:
        raise ValueError(
            "Server did not return a CA chain; ATAK/iTAK data packages need a trust store."
        )

    stream_host = streaming_host or hostname
    desc = stream_description or f"{username} @ TAK Server"
    callsign = location_callsign if location_callsign is not None else username

    def _write_layout_zip(layout: str, manifest_label: str) -> str:
        pref_xml = build_connection_config_pref_xml(
            stream_description=desc,
            streaming_host=stream_host,
            streaming_port=streaming_port,
            ca_password=pw,
            client_password=pw,
            location_callsign=callsign,
            location_team=location_team,
            atak_role_type=atak_role_type,
            package_layout=layout,
        )
        man_xml = build_connection_manifest_xml(
            uid=str(uuid.uuid4()),
            display_name=manifest_label,
            on_receive_delete=on_receive_delete,
            package_layout=layout,
        )
        zip_bytes = build_connection_data_package_zip(
            config_pref_xml=pref_xml,
            manifest_xml=man_xml,
            client_p12_path=client_p12,
            trust_p12_path=trust_p12,
            package_layout=layout,
        )
        suffix = "itak" if layout == "itak" else "atak"
        zpath = os.path.join(pkg_root, f"{stem}-{suffix}-connection.zip")
        with open(zpath, "wb") as zf:
            zf.write(zip_bytes)
        os.chmod(zpath, 0o644)
        return zpath

    atak_manifest_label = f"{stem}-atak-connection.zip"
    itak_manifest_label = f"{stem}-itak-connection.zip"
    atak_zip = _write_layout_zip("atak", atak_manifest_label)
    itak_zip = _write_layout_zip("itak", itak_manifest_label)

    return {
        "success": True,
        "package_folder": pkg_root,
        "package_stem": stem,
        "username": username,
        "hostname": hostname,
        "pkcs12_password": pw,
        "streaming_connect_string": f"{stream_host}:{streaming_port}:ssl",
        "data_package_zip": atak_zip,
        "data_package_itak_zip": itak_zip,
        "enrollment": artifacts,
    }
