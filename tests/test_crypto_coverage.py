#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Behavioural coverage tests for pytak.crypto_functions and crypto_classes."""

import asyncio
import datetime
import json
import logging
import os
import ssl
import stat
from unittest import mock

import pytest

pytest.importorskip("cryptography")
aiohttp = pytest.importorskip("aiohttp")

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from pytak import crypto_classes, crypto_functions
from pytak.crypto_classes import CertificateEnrollment

PASSWORD = "test-p12-pass"
DOMAIN = "takserver.example.com"


# --- builders --------------------------------------------------------------


@pytest.fixture(scope="module")
def pki():
    """A CA plus a client key/cert signed by it, generated at test time."""
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-ca")])
    client_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "client")])
    now = datetime.datetime.now(datetime.timezone.utc)

    def build(subject, pub, issuer, signer):
        return (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(pub)
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=1))
            .sign(signer, hashes.SHA256())
        )

    ca_cert = build(ca_name, ca_key.public_key(), ca_name, ca_key)
    client_cert = build(client_name, client_key.public_key(), ca_name, ca_key)
    return {
        "ca_key": ca_key,
        "ca_cert": ca_cert,
        "key": client_key,
        "cert": client_cert,
    }


def _p12(key, cert, cas, password=PASSWORD):
    enc = (
        serialization.BestAvailableEncryption(password.encode())
        if password
        else serialization.NoEncryption()
    )
    return pkcs12.serialize_key_and_certificates(b"test", key, cert, cas, enc)


def _write(path, data):
    path.write_bytes(data)
    return str(path)


def _pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


def _headerless(cert):
    return "".join(
        line for line in _pem(cert).splitlines() if not line.startswith("-----")
    )


# --- crypto_functions ------------------------------------------------------


def test_save_pem_to_explicit_dest(tmp_path):
    dest = tmp_path / "x.pem"
    assert crypto_functions.save_pem(b"PEMDATA", str(dest)) == str(dest)
    assert dest.read_bytes() == b"PEMDATA"


def test_save_pem_to_tempfile():
    path = crypto_functions.save_pem(b"PEMDATA")
    try:
        assert path.endswith(".pem")
        with open(path, "rb") as fd:
            assert fd.read() == b"PEMDATA"
    finally:
        os.remove(path)


def test_functions_require_cryptography(monkeypatch, tmp_path):
    monkeypatch.setattr(crypto_functions, "USE_CRYPTOGRAPHY", False)
    with pytest.raises(ValueError, match="cryptography"):
        crypto_functions.load_cert("x.p12", PASSWORD)
    with pytest.raises(ValueError, match="cryptography"):
        crypto_functions.convert_cert("x.p12", PASSWORD)
    with pytest.raises(ValueError, match="cryptography"):
        crypto_functions.serialize_trust_pkcs12([], PASSWORD)
    with pytest.raises(ValueError, match="cryptography"):
        crypto_functions.write_enrollment_artifacts("x", "p", str(tmp_path), "s")


def test_convert_cert_success(tmp_path, pki):
    p12 = _write(tmp_path / "c.p12", _p12(pki["key"], pki["cert"], [pki["ca_cert"]]))
    paths = crypto_functions.convert_cert(p12, PASSWORD)
    try:
        with open(paths["pk_pem_path"], "rb") as fd:
            key = serialization.load_pem_private_key(fd.read(), None)
        assert key.private_numbers() == pki["key"].private_numbers()
        with open(paths["cert_pem_path"], "rb") as fd:
            chain = x509.load_pem_x509_certificates(fd.read())
        assert [c.subject for c in chain] == [
            pki["cert"].subject,
            pki["ca_cert"].subject,
        ]
        with open(paths["ca_pem_path"], "rb") as fd:
            assert x509.load_pem_x509_certificate(fd.read()) == pki["ca_cert"]
    finally:
        for path in paths.values():
            os.remove(path)


def test_convert_cert_cleans_partial_output_and_tolerates_missing(
    tmp_path, pki, monkeypatch
):
    """A failure mid-way removes written files; vanished files are ignored."""
    p12 = _write(tmp_path / "c.p12", _p12(pki["key"], pki["cert"], [pki["ca_cert"]]))
    written = tmp_path / "written.pem"
    calls = []

    def flaky_save_pem(pem, dest=None):
        calls.append(pem)
        if len(calls) == 1:
            written.write_bytes(pem)
            return str(written)
        if len(calls) == 2:
            return str(tmp_path / "already-gone.pem")
        raise OSError("No space left on device")

    monkeypatch.setattr(crypto_functions, "save_pem", flaky_save_pem)
    with pytest.raises(OSError, match="No space left"):
        crypto_functions.convert_cert(p12, PASSWORD)
    assert not written.exists()


def test_pkcs12_friendly_name(pki):
    assert crypto_functions._pkcs12_friendly_name(pki["ca_cert"]) == b"test-ca"

    bad = mock.MagicMock()
    bad.subject.get_attributes_for_oid.side_effect = ValueError("bad")
    assert crypto_functions._pkcs12_friendly_name(bad) is None

    no_cn = mock.MagicMock()
    no_cn.subject.get_attributes_for_oid.return_value = []
    assert crypto_functions._pkcs12_friendly_name(no_cn) is None


def test_serialize_pkcs12_bundle_unencrypted(pki):
    blob = crypto_functions.serialize_pkcs12_bundle(
        private_key=pki["key"],
        certificate=pki["cert"],
        ca_certificates=None,
        passphrase="",
    )
    key, cert, cas = pkcs12.load_key_and_certificates(blob, None)
    assert cert == pki["cert"]
    assert cas == []


def test_serialize_trust_pkcs12(pki):
    with pytest.raises(ValueError, match="No CA certificates"):
        crypto_functions.serialize_trust_pkcs12([], PASSWORD)
    blob = crypto_functions.serialize_trust_pkcs12([pki["ca_cert"]], PASSWORD)
    key, cert, cas = pkcs12.load_key_and_certificates(blob, PASSWORD.encode())
    assert key is None and cert is None
    assert cas == [pki["ca_cert"]]


def test_rewrite_pkcs12_atak_compatible(tmp_path, pki):
    p12 = _write(tmp_path / "c.p12", _p12(pki["key"], pki["cert"], [pki["ca_cert"]]))
    crypto_functions.rewrite_pkcs12_atak_compatible(p12, PASSWORD)
    with open(p12, "rb") as fd:
        loaded = pkcs12.load_pkcs12(fd.read(), PASSWORD.encode())
    assert loaded.cert.certificate == pki["cert"]
    assert loaded.cert.friendly_name == b"c.p12"
    assert [c.certificate for c in loaded.additional_certs] == [pki["ca_cert"]]
    assert stat.S_IMODE(os.stat(p12).st_mode) == 0o600


def test_rewrite_pkcs12_without_cert_raises(tmp_path, pki):
    p12 = _write(tmp_path / "k.p12", _p12(pki["key"], None, None))
    with pytest.raises(ValueError, match="No certificate"):
        crypto_functions.rewrite_pkcs12_atak_compatible(p12, PASSWORD)


def test_write_enrollment_artifacts_without_cert_raises(tmp_path, pki):
    p12 = _write(tmp_path / "k.p12", _p12(pki["key"], None, None))
    with pytest.raises(ValueError, match="No certificate"):
        crypto_functions.write_enrollment_artifacts(
            p12, PASSWORD, str(tmp_path / "o"), "s"
        )


def test_write_enrollment_artifacts_without_ca(tmp_path, pki):
    p12 = _write(tmp_path / "c.p12", _p12(pki["key"], pki["cert"], None))
    res = crypto_functions.write_enrollment_artifacts(
        p12, PASSWORD, str(tmp_path / "o"), "s"
    )
    assert res["ca_bundle_path"] is None
    assert res["pkcs12_truststore_path"] is None
    assert os.path.exists(res["pkcs12_path"])


def test_write_enrollment_artifacts_with_ca(tmp_path, pki):
    p12 = _write(tmp_path / "c.p12", _p12(pki["key"], pki["cert"], [pki["ca_cert"]]))
    res = crypto_functions.write_enrollment_artifacts(
        p12, PASSWORD, str(tmp_path / "o"), "s"
    )
    with open(res["ca_bundle_path"], "rb") as fd:
        assert x509.load_pem_x509_certificates(fd.read()) == [pki["ca_cert"]]
    with open(res["pkcs12_truststore_path"], "rb") as fd:
        key, cert, cas = pkcs12.load_key_and_certificates(fd.read(), PASSWORD.encode())
    assert key is None and cert is None and cas == [pki["ca_cert"]]
    assert stat.S_IMODE(os.stat(res["private_key_path"]).st_mode) == 0o600
    assert res["pkcs12_password"] == PASSWORD


def test_convert_p12_to_pem_success(tmp_path, pki):
    p12 = _write(tmp_path / "c.p12", _p12(pki["key"], pki["cert"], [pki["ca_cert"]]))
    key_path, cert_path = crypto_functions.convert_p12_to_pem(p12, PASSWORD)
    assert key_path == p12 + ".key.pem"
    assert cert_path == p12 + ".cert.pem"
    with open(key_path, "rb") as fd:
        data = fd.read()
    assert data.startswith(b"-----BEGIN RSA PRIVATE KEY-----")
    key = serialization.load_pem_private_key(data, None)
    assert key.private_numbers() == pki["key"].private_numbers()
    with open(cert_path, "rb") as fd:
        chain = x509.load_pem_x509_certificates(fd.read())
    assert chain == [pki["cert"], pki["ca_cert"]]


def test_create_ssl_context(tmp_path, pki, capsys):
    p12 = _write(tmp_path / "c.p12", _p12(pki["key"], pki["cert"], None))
    ctx = crypto_functions.create_ssl_context(p12, PASSWORD)
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE
    assert "Converted PKCS#12 to PEM" in capsys.readouterr().out


# --- crypto_classes: fakes -------------------------------------------------


class FakeResponse:
    def __init__(self, status=200, body=b"", json_data=None, json_exc=None):
        self.status = status
        self._body = body
        self._json_data = json_data
        self._json_exc = json_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError("HTTP %d" % self.status)

    async def text(self):
        return self._body.decode("utf-8")

    async def read(self):
        return self._body

    async def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._json_data


class FakeSession:
    """Minimal aiohttp.ClientSession stand-in; post responses are queued."""

    def __init__(self, get_response=None, post_responses=()):
        self.get_response = get_response
        self.post_responses = list(post_responses)
        self.gets = []
        self.posts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def get(self, url, **kwargs):
        self.gets.append(url)
        return self.get_response

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        resp = self.post_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


V1_URL = "https://%s:8446/Marti/api/tls/signClient?clientUid=test" % DOMAIN
V2_URL = "https://%s:8446/Marti/api/tls/signClient/v2?clientUid=test" % DOMAIN

CONFIG_XML = (
    '<certificateConfig xmlns="com.bbn.marti.config"><nameEntries>'
    '<nameEntry name="O" value="TAK"/><nameEntry name="OU" value="Unit"/>'
    "</nameEntries></certificateConfig>"
)


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Redirect ~ so debug/default output never touches the real home dir."""
    h = tmp_path / "home"
    (h / "Downloads").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(h))
    return h


@pytest.fixture
def enrollment():
    return CertificateEnrollment()


def _server_p12(pki):
    return _p12(None, pki["cert"], [pki["ca_cert"]], password="atakatak")


def _load_out(path, password):
    with open(str(path), "rb") as fd:
        return pkcs12.load_key_and_certificates(
            fd.read(), password.encode() if password else None
        )


# --- crypto_classes: tests -------------------------------------------------


def test_init_requires_dependencies(monkeypatch):
    monkeypatch.setattr(crypto_classes, "USE_CRYPTOGRAPHY", False)
    with pytest.raises(ValueError, match="cryptography"):
        CertificateEnrollment()
    monkeypatch.setattr(crypto_classes, "USE_CRYPTOGRAPHY", True)
    monkeypatch.setattr(crypto_classes, "USE_AIOHTTP", False)
    with pytest.raises(ValueError, match="aiohttp"):
        CertificateEnrollment()


def test_generate_key(enrollment):
    key = enrollment._generate_key(key_size=1024)
    assert key.key_size == 1024
    assert enrollment._generate_key(key_size=1) is None


def test_create_session_currently_always_disables_verification(enrollment):
    """Current behaviour: trust_all is forced True (see crypto_classes)."""

    async def run():
        session = enrollment._create_session(trust_all=False)
        try:
            assert isinstance(session, aiohttp.ClientSession)
            assert session.connector._ssl is False
            assert session.timeout.total == 30
        finally:
            await session.close()

    asyncio.run(run())


def test_parse_config_xml_formats(enrollment):
    assert enrollment._parse_config_xml(CONFIG_XML) == {"O": "TAK", "OU": "Unit"}
    legacy = '<config><entry name="C" value="US"/><entry name="x"/></config>'
    assert enrollment._parse_config_xml(legacy) == {"C": "US"}
    assert enrollment._parse_config_xml("<not xml") == {}


def test_create_csr_from_config_all_fields(enrollment, pki):
    config = {"CN": "u", "O": "o", "OU": "ou", "C": "US", "ST": "st", "L": "l"}
    pem = enrollment._create_csr_from_config(config, pki["key"])
    csr = x509.load_pem_x509_csr(pem.encode())
    assert csr.is_signature_valid
    attrs = {a.oid: a.value for a in csr.subject}
    assert attrs == {
        NameOID.COMMON_NAME: "u",
        NameOID.ORGANIZATION_NAME: "o",
        NameOID.ORGANIZATIONAL_UNIT_NAME: "ou",
        NameOID.COUNTRY_NAME: "US",
        NameOID.STATE_OR_PROVINCE_NAME: "st",
        NameOID.LOCALITY_NAME: "l",
    }


def test_generate_csr_success(enrollment, pki):
    session = FakeSession(get_response=FakeResponse(200, CONFIG_XML.encode()))
    pem = asyncio.run(
        enrollment._generate_csr("alice", "pw", session, DOMAIN, pki["key"])
    )
    assert session.gets == ["https://%s:8446/Marti/api/tls/config" % DOMAIN]
    csr = x509.load_pem_x509_csr(pem.encode())
    assert csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == ("alice")


@pytest.mark.parametrize(
    "response", [FakeResponse(200, b"<empty/>"), FakeResponse(401, b"")]
)
def test_generate_csr_failure_returns_none(enrollment, pki, response):
    session = FakeSession(get_response=response)
    assert (
        asyncio.run(enrollment._generate_csr("a", "b", session, DOMAIN, pki["key"]))
        is None
    )


def test_begin_enrollment_end_to_end_v2(enrollment, pki, tmp_path, monkeypatch):
    session = FakeSession(
        get_response=FakeResponse(200, CONFIG_XML.encode()),
        post_responses=[
            FakeResponse(
                200,
                json_data={
                    "signedCert": _headerless(pki["cert"]),
                    "ca0": _headerless(pki["ca_cert"]),
                    "ca1": "",
                },
            )
        ],
    )
    monkeypatch.setattr(enrollment, "_create_session", lambda trust_all: session)
    monkeypatch.setattr(enrollment, "_generate_key", lambda: pki["key"])
    out = tmp_path / "nested" / "client.p12"
    asyncio.run(
        enrollment.begin_enrollment(
            DOMAIN, "alice", "pw", output_path=str(out), passphrase="pp"
        )
    )
    assert session.posts[0][0] == V2_URL
    assert session.posts[0][1]["headers"] == {"Content-Type": "application/pkcs10"}
    key, cert, cas = _load_out(out, "pp")
    assert cert == pki["cert"]
    assert cas == [pki["ca_cert"]]


def test_begin_enrollment_key_failure(enrollment, monkeypatch, caplog):
    monkeypatch.setattr(enrollment, "_generate_key", lambda: None)
    called = []
    monkeypatch.setattr(
        enrollment, "_enrollment_process", lambda *a, **k: called.append(a)
    )
    asyncio.run(enrollment.begin_enrollment(DOMAIN, "a", "b"))
    assert called == []
    assert "Failed to generate private key" in caplog.text


def test_enrollment_process_skips_signing_without_csr(enrollment, pki, monkeypatch):
    session = FakeSession(get_response=FakeResponse(500, b""))
    monkeypatch.setattr(enrollment, "_create_session", lambda trust_all: session)
    asyncio.run(enrollment._enrollment_process(DOMAIN, "a", "b", False, pki["key"]))
    assert session.posts == []


def test_enrollment_process_swallows_errors(enrollment, pki, monkeypatch, caplog):
    """Current behaviour: failures are logged, not raised."""

    def boom(trust_all):
        raise RuntimeError("no session")

    monkeypatch.setattr(enrollment, "_create_session", boom)
    asyncio.run(enrollment._enrollment_process(DOMAIN, "a", "b", False, pki["key"]))
    assert "Error in enrollment process: no session" in caplog.text


def test_process_csr_v2_json_content_type_fallback(enrollment, pki, tmp_path):
    body = json.dumps({"signedCert": _pem(pki["cert"])}).encode()
    session = FakeSession(
        post_responses=[FakeResponse(200, body, json_exc=ValueError("ctype"))]
    )
    out = tmp_path / "c.p12"
    asyncio.run(
        enrollment._process_csr(
            "a", "b", session, DOMAIN, "CSR", pki["key"], output_path=str(out)
        )
    )
    key, cert, cas = _load_out(out, None)
    assert cert == pki["cert"]


def test_process_csr_v2_http_error_falls_back_to_v1(enrollment, pki, tmp_path):
    session = FakeSession(
        post_responses=[FakeResponse(404), FakeResponse(200, _server_p12(pki))]
    )
    out = tmp_path / "c.p12"
    asyncio.run(
        enrollment._process_csr(
            "a",
            "b",
            session,
            DOMAIN,
            "CSR",
            pki["key"],
            output_path=str(out),
            passphrase="pp",
        )
    )
    assert [p[0] for p in session.posts] == [V2_URL, V1_URL]
    key, cert, cas = _load_out(out, "pp")
    assert cert == pki["cert"]


def test_process_csr_v2_exception_falls_back_to_v1(enrollment, pki, tmp_path):
    session = FakeSession(
        post_responses=[
            aiohttp.ClientError("refused"),
            FakeResponse(200, _server_p12(pki)),
        ]
    )
    out = tmp_path / "c.p12"
    asyncio.run(
        enrollment._process_csr(
            "a", "b", session, DOMAIN, "CSR", pki["key"], output_path=str(out)
        )
    )
    assert [p[0] for p in session.posts] == [V2_URL, V1_URL]
    assert out.exists()


def test_process_csr_v1_failure_does_not_recurse(enrollment, pki, caplog):
    session = FakeSession(post_responses=[FakeResponse(500)])
    asyncio.run(
        enrollment._process_csr("a", "b", session, DOMAIN, "CSR", pki["key"], False)
    )
    assert [p[0] for p in session.posts] == [V1_URL]
    assert "failed with status: 500" in caplog.text


def test_process_csr_fallback_error_is_logged(enrollment, pki, monkeypatch, caplog):
    session = FakeSession(post_responses=[aiohttp.ClientError("v2 down")])
    real = enrollment._process_csr

    async def wrapped(*args, **kwargs):
        if kwargs.get("use_v2") is False:
            raise RuntimeError("v1 down")
        return await real(*args, **kwargs)

    monkeypatch.setattr(enrollment, "_process_csr", wrapped)
    asyncio.run(enrollment._process_csr("a", "b", session, DOMAIN, "CSR", pki["key"]))
    assert "Both v2 and v1 endpoints failed: v1 down" in caplog.text


def test_json_response_without_signed_cert(enrollment, pki, monkeypatch, caplog):
    created = []
    monkeypatch.setattr(
        enrollment, "_create_client_certificate", lambda *a: created.append(a)
    )
    asyncio.run(enrollment._process_json_certificate_response({}, pki["key"]))
    assert created == []
    assert "No 'signedCert'" in caplog.text


def test_json_response_invalid_cert_saves_debug_files(enrollment, pki, home):
    data = {"signedCert": "bm90IGEgY2VydA==", "ca0": _pem(pki["ca_cert"])}
    asyncio.run(enrollment._process_json_certificate_response(data, pki["key"]))
    debug = home / "Downloads" / "cert_debug"
    assert "-----BEGIN CERTIFICATE-----" in (debug / "raw_signed_cert.pem").read_text()
    assert "=== CA Certificate 0 ===" in (debug / "raw_ca_certs.txt").read_text()
    assert not (home / "Downloads" / "clientCert.p12").exists()


def test_json_response_unexpected_error_is_logged(enrollment, pki, caplog):
    asyncio.run(
        enrollment._process_json_certificate_response({"signedCert": 1}, pki["key"])
    )
    assert "Error processing JSON certificate response" in caplog.text


def test_pkcs12_response_cert_in_additional_certs(enrollment, pki, tmp_path):
    """Unpaired certs land in additional certs; the first is used as client."""
    server = _p12(None, None, [pki["cert"], pki["ca_cert"]], password="atakatak")
    out = tmp_path / "c.p12"
    asyncio.run(
        enrollment._process_pkcs12_certificate_response(
            server, pki["key"], str(out), "pp"
        )
    )
    key, cert, cas = _load_out(out, "pp")
    assert cert == pki["cert"]
    assert cas == [pki["ca_cert"]]


def test_pkcs12_response_single_cert_no_cas(enrollment, pki, tmp_path):
    server = _p12(None, None, [pki["cert"]], password="atakatak")
    out = tmp_path / "c.p12"
    asyncio.run(
        enrollment._process_pkcs12_certificate_response(server, pki["key"], str(out))
    )
    key, cert, cas = _load_out(out, None)
    assert cert == pki["cert"]
    assert cas == []


def test_pkcs12_response_without_cert(enrollment, pki, tmp_path, caplog):
    server = _p12(pki["key"], None, None, password="atakatak")
    out = tmp_path / "c.p12"
    asyncio.run(
        enrollment._process_pkcs12_certificate_response(server, pki["key"], str(out))
    )
    assert not out.exists()
    assert "No certificate found in PKCS12 response" in caplog.text


def test_pkcs12_response_garbage_saved_for_debugging(enrollment, pki, home, caplog):
    asyncio.run(enrollment._process_pkcs12_certificate_response(b"garbage", pki["key"]))
    assert (home / "Downloads" / "server_response.p12").read_bytes() == b"garbage"
    assert "Failed to load as PKCS12" in caplog.text


def test_create_client_certificate_default_path(enrollment, pki, home):
    enrollment._create_client_certificate(
        _pem(pki["cert"]), [_pem(pki["ca_cert"])], pki["key"]
    )
    key, cert, cas = _load_out(home / "Downloads" / "clientCert.p12", None)
    assert cert == pki["cert"]
    assert cas == [pki["ca_cert"]]


@pytest.mark.parametrize("bad", ["cert", "ca"])
def test_create_client_certificate_bad_pem(enrollment, pki, tmp_path, caplog, bad):
    cert_pem = "junk" if bad == "cert" else _pem(pki["cert"])
    ca_pems = ["junk"] if bad == "ca" else []
    out = tmp_path / "c.p12"
    enrollment._create_client_certificate(cert_pem, ca_pems, pki["key"], str(out))
    assert not out.exists()
    assert "Error creating client certificate" in caplog.text


def test_fix_pem_formatting(enrollment, pki):
    pem = _pem(pki["cert"])
    body = _headerless(pki["cert"])
    assert enrollment._fix_pem_formatting("") == ""
    assert enrollment._fix_pem_formatting(body) == pem
    assert enrollment._fix_pem_formatting(pem.replace("\n", "\\r\\n")) == pem
    single = "-----BEGIN CERTIFICATE-----" + body + "-----END CERTIFICATE-----"
    assert enrollment._fix_pem_formatting(single) == pem
    broken = "-----BEGIN CERTIFICATE-----\nAAAA\nBBBB-----"
    assert enrollment._fix_pem_formatting(broken) == broken


def test_module_main_runs_example_enrollment(monkeypatch):
    calls = []

    async def fake_begin(self, *args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(CertificateEnrollment, "begin_enrollment", fake_begin)
    asyncio.run(crypto_classes.main())
    assert calls == [
        (
            ("example.com", "testuser", "testpass"),
            {
                "trust_all": True,
                "use_v2": True,
                "output_path": "./my_client_cert.p12",
            },
        )
    ]


@pytest.fixture(autouse=True)
def _caplog_level(caplog):
    caplog.set_level(logging.DEBUG, logger="pytak.crypto_classes")
