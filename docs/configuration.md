# Configuration

PyTAK configuration can be set in two ways:

1. **Environment variables** — set before running your script
2. **INI-style config file** — typically `config.ini`, passed via your `ConfigParser`

Both methods work identically. Environment variables take precedence.

**Example `config.ini`:**

```ini
[mytool]
COT_URL = tls://takserver.example.com:8089
PYTAK_TLS_CLIENT_CERT = /etc/pytak/client.pem
DEBUG = 0
```

**Equivalent environment variables:**

```sh
export COT_URL=tls://takserver.example.com:8089
export PYTAK_TLS_CLIENT_CERT=/etc/pytak/client.pem
export DEBUG=0
```

---

## Core Parameters

### `COT_URL`

**Default:** `udp+wo://239.2.3.1:6969` (ATAK Mesh SA multicast, write-only)

The destination for CoT events. Supported URL schemes:

| Scheme | Description |
|---|---|
| `tcp://host:port` | TCP unicast (plain text) |
| `tls://host:port` | TLS unicast (encrypted) |
| `udp://group:port` | UDP multicast (Mesh SA) |
| `udp://host:port` | UDP unicast |
| `udp+broadcast://network:port` | UDP broadcast |
| `udp+wo://host:port` | UDP write-only (no port binding) |
| `log://stdout` | Print to stdout (debug) |
| `log://stderr` | Print to stderr (debug) |
| `marti://host:port` | TAK Server Marti REST API (TLS) |
| `marti+http://host:port` | TAK Server Marti REST API (plain HTTP) |
| `tak://...` | TAK enrollment deep-link (see below) |

!!! tip "Port already in use?"
    Add the `+wo` modifier (`udp+wo://`) to run write-only without binding the port. This lets multiple PyTAK applications share a network interface.

---

### `TAK_PROTO`

**Default:** `0`

TAK Protocol version for CoT output:

| Value | Protocol |
|---|---|
| `0` | TAK Protocol v0 — plain XML (default, recommended) |
| `1` | TAK Protocol v1 — Protobuf (requires `pytak[with_takproto]`) |

!!! warning "Protobuf compatibility"
    TAK Protocol v1 may not work with all TAK clients (notably some versions of iTAK). Stick with `TAK_PROTO=0` unless you have a specific need for Protobuf.

---

### `DEBUG`

**Default:** `0`

Set to `1` to enable verbose debug logging.

---

### `FTS_COMPAT`

**Default:** `0`

Set to `1` to enable FreeTAKServer compatibility mode. PyTAK will sleep a random number of seconds between transmissions to avoid FTS's built-in rate-limit / anti-DoS protections.

---

### `PYTAK_SLEEP`

**Default:** `0` (disabled)

Sleep interval in whole seconds between CoT transmissions. Use instead of `FTS_COMPAT` for a fixed sleep period.

```ini
PYTAK_SLEEP = 3
```

---

### `PYTAK_NO_HELLO`

**Default:** `False`

Set to `True` to suppress the initial "Hello" CoT event that PyTAK sends when connecting to a TCP or UDP endpoint. Useful for deployments that require a quiet startup.

---

### `COT_STALE`

**Default:** `120` (2 minutes)

CoT event stale time in seconds. Events older than this are considered expired by TAK clients.

---

### `MAX_OUT_QUEUE`

**Default:** `100`

Maximum number of outgoing CoT events to buffer before dropping the oldest. Increase this if your sender produces bursts faster than the network can absorb them.

---

### `MAX_IN_QUEUE`

**Default:** `500`

Maximum number of incoming CoT events to buffer. Increase this if your receiver is processing events slower than they arrive.

---

## Multicast Parameters

### `PYTAK_MULTICAST_LOCAL_ADDR`

**Default:** `0.0.0.0`

On systems with multiple network interfaces, specifies which interface IP to use for multicast. Set this to the IP of the interface connected to your TAK network.

```ini
PYTAK_MULTICAST_LOCAL_ADDR = 192.168.1.100
```

---

### `PYTAK_MULTICAST_TTL`

**Default:** `1`

Time-to-live for multicast packets. Increase this if your TAK client is more than one network hop away (e.g. inside a VM or container with an overlay network).

---

## TAK Data Package Support

### `PREF_PACKAGE`

!!! note "Requires `pytak[with_crypto]`"
    Install with `pip install pytak[with_crypto]` or `apt install python3-cryptography`.

Path to a TAK Data Package `.zip` file containing TAK Server connection settings, TLS certificates, etc. PyTAK will import these settings automatically on startup.

```ini
PREF_PACKAGE = /path/to/MyServer.zip
```

Or pass via command line argument: `-p MyServer.zip`

---

## tak:// Onboarding URL {#tak-onboarding-url}

!!! note "Requires `pytak[with_aiohttp]` and `pytak[with_crypto]`"

PyTAK supports TAK enrollment deep-link URLs in the format used by ATAK's QR-code onboarding flow:

```
tak://com.atakmap.app/enroll?host=<host>&username=<user>&token=<secret>
```

Set this as `COT_URL` (or the `TAK_URL` environment variable):

```ini
COT_URL = tak://com.atakmap.app/enroll?host=takserver.example.com&username=myuser&token=mytoken
```

CLI usage:

```sh
pytak "tak://com.atakmap.app/enroll?host=takserver.example.com&username=myuser&token=mytoken"
```

To force a specific WebSocket/Marti port, include it in `host=`:

```sh
pytak "tak://com.atakmap.app/enroll?host=takserver.example.com:8443&username=myuser&token=mytoken"
```

What PyTAK does with a `tak://` URL:

1. Parses the host, username, and token from the URL
2. Checks `~/.pytak/certs/` for a valid cached certificate
3. If no valid cert is cached, performs a full CSR → PKCS#12 enrollment against the TAK Server
4. Caches the certificate and passphrase to disk
5. Automatically sets `COT_URL` to `wss://<host>:8443/takproto/1` by default and configures TLS using the enrolled cert

If the onboarding URL explicitly includes a port in `host=`, PyTAK uses that port instead. When the explicit port is the TAK streaming port (`8089`), PyTAK keeps `tls://<host>:8089`.

Certificates are re-enrolled automatically when they are within 7 days of expiry.

---

## marti:// REST API Transport

!!! note "Requires `pytak[with_aiohttp]`"

Send and receive CoT via the TAK Server Marti REST API instead of a raw TCP/TLS socket:

```ini
# TLS (default port 8443)
COT_URL = marti://takserver.example.com:8443

# Plain HTTP
COT_URL = marti+http://takserver.example.com:8080
```

Additional Marti parameters:

| Parameter | Default | Description |
|---|---|---|
| `MARTI_COT_UID` | host ID | Client UID used to filter received CoT |
| `MARTI_POLL_INTERVAL` | `5` | Seconds between polling for new CoT events |
| `MARTI_POLL_SECONDS_AGO` | `30` | How far back (seconds) to fetch events per poll |

---

## TLS Support

PyTAK supports full mutual-TLS (mTLS) connections to TAK Servers. Use `tls://` in `COT_URL`.

**Minimum TLS configuration:**

```ini
COT_URL = tls://takserver.example.com:8089
PYTAK_TLS_CLIENT_CERT = /etc/pytak/client.pem
```

The matching `CoreConfig.xml` stanza on the TAK Server:

```xml
<input auth="x509" _name="tlsx509" protocol="tls" port="8089" archive="false"/>
```

!!! note "Certificate format"
    All cert and key files must be in unencrypted PEM format, **or** use a PKCS#12 `.p12` file combined with `PYTAK_TLS_CLIENT_PASSWORD`.

### TLS Parameters

#### `PYTAK_TLS_CLIENT_CERT`

Path to the PEM-format client certificate. This file may contain both the certificate and the private key, or the certificate alone (in which case also set `PYTAK_TLS_CLIENT_KEY`).

```ini
PYTAK_TLS_CLIENT_CERT = /etc/pytak/client_cert_and_key.pem
```

---

#### `PYTAK_TLS_CLIENT_KEY` *(optional)*

Path to the PEM-format client private key, if not bundled with `PYTAK_TLS_CLIENT_CERT`.

---

#### `PYTAK_TLS_CLIENT_CAFILE` *(optional)*

Path to a PEM-format CA trust chain file. Required when the TAK Server uses a private CA that is not in the system trust store.

```ini
PYTAK_TLS_CLIENT_CAFILE = /etc/pytak/ca-chain.pem
```

---

#### `PYTAK_TLS_CLIENT_PASSWORD` *(optional)*

Password for an encrypted private key or a PKCS#12 (`.p12`) certificate file.

```ini
PYTAK_TLS_CLIENT_PASSWORD = atakatak
```

---

#### `PYTAK_TLS_DONT_VERIFY`

**Default:** `0` (verify)

Set to `1` to disable remote certificate verification. **Use with caution** — this makes the connection vulnerable to man-in-the-middle attacks. A WARNING is printed when enabled.

---

#### `PYTAK_TLS_DONT_CHECK_HOSTNAME`

**Default:** `0` (check)

Set to `1` to disable TLS hostname (CN) verification. A WARNING is printed when enabled.

---

#### `PYTAK_TLS_SERVER_EXPECTED_HOSTNAME` *(optional)*

Expected hostname or Common Name (CN) of the TAK Server certificate. Only used when hostname verification is active.

---

#### `PYTAK_TLS_CLIENT_CIPHERS` *(optional)*

**Default:** `ALL`

Colon-separated list of TLS cipher suites. Example for FIPS-only ciphers:

```ini
PYTAK_TLS_CLIENT_CIPHERS = ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384
```

---

## Certificate Enrollment Parameters

!!! note "Requires `pytak[with_aiohttp]` and `pytak[with_crypto]`"

These parameters trigger automatic certificate enrollment from a TAK Server. Alternatively, use a `tak://` URL which handles all of this automatically.

#### `PYTAK_TLS_CERT_ENROLLMENT_USERNAME`

TAK Server username for certificate enrollment.

#### `PYTAK_TLS_CERT_ENROLLMENT_PASSWORD`

TAK Server password for certificate enrollment.

#### `PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE`

Passphrase to protect the enrolled certificate. If not set, a random passphrase is generated and cached to disk alongside the certificate.
