# Troubleshooting

## CoT events not appearing in TAK

Work through these steps in order:

**1. Verify CoT is being generated**

Set `COT_URL=log://stdout` and run your tool. If CoT XML prints to the console, PyTAK is working and the problem is network connectivity or configuration.

```sh
COT_URL=log://stdout python3 send.py
```

**2. Connect directly to an EUD**

Bypass the TAK Server and connect directly to an ATAK/iTAK/WinTAK device on the same network:

```ini
COT_URL = tcp://192.168.1.50:4242
```

Replace `192.168.1.50` with the device's IP. In ATAK, enable the streaming server under *Settings → Network → Streaming*.

**3. Check multicast support**

If using `udp://` (Mesh SA), confirm your network switch and router support multicast. Many managed switches disable multicast by default. Try switching to `tcp://` or `udp+wo://` to rule out multicast issues.

**4. Enable debug logging**

```sh
DEBUG=1 python3 send.py
```

Look for connection errors, dropped packets, or queue warnings in the output.

---

## `Enter PEM pass phrase:` prompt

This prompt appears when your private key is password-protected (the default when using TAK Server's `makeCert.sh`).

**Option 1 — Set the password in config (recommended):**

```ini
PYTAK_TLS_CLIENT_PASSWORD = atakatak
```

**Option 2 — Remove the passphrase from the key:**

```sh
openssl rsa -in pytak.key -out pytak.nopass.key
```

Then point `PYTAK_TLS_CLIENT_KEY` at the new file.

**Option 3 — Accept the prompt** and enter the password each time PyTAK starts.

---

## `certificate verify failed` error

```
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
self signed certificate in certificate chain
```

The TAK Server is using a self-signed certificate or a certificate signed by a private CA that your system doesn't trust. This is expected for most TAK Server deployments.

**Option 1 — Provide the CA chain (recommended):**

Export your TAK Server's CA certificate (`ca.pem`) and set:

```ini
PYTAK_TLS_CLIENT_CAFILE = /etc/pytak/ca.pem
```

The CA cert is typically found at `/opt/tak/certs/files/ca.pem` on the TAK Server.

**Option 2 — Disable verification (development only):**

```ini
PYTAK_TLS_DONT_VERIFY = 1
```

!!! warning
    Disabling verification removes protection against man-in-the-middle attacks. Only use in isolated test environments.

---

## `hostname mismatch` / CN verification error

```
ssl.SSLCertVerificationError: hostname ... doesn't match
```

The certificate's Common Name (CN) doesn't match the hostname in `COT_URL`.

**Option 1 — Set the expected hostname:**

```ini
PYTAK_TLS_SERVER_EXPECTED_HOSTNAME = takserver.example.com
```

**Option 2 — Disable hostname checking (development only):**

```ini
PYTAK_TLS_DONT_CHECK_HOSTNAME = 1
```

---

## `aiohttp` not installed

```
ImportError: Marti HTTP transport requires aiohttp. Install with: pip install pytak[with_aiohttp]
```

The `marti://` URL scheme and `tak://` certificate enrollment require the `aiohttp` extra:

```sh
pip install pytak[with_aiohttp]
```

Or on Debian/Ubuntu:

```sh
sudo apt install -y python3-aiohttp
```

---

## `takproto` not installed

```
TAK_PROTO is set to '1', but the 'takproto' Python module is not installed.
```

Install the `takproto` extra:

```sh
pip install pytak[with_takproto]
```

---

## Queue full warnings

```
Queue full, dropping oldest data. Consider raising MAX_IN_QUEUE or MAX_OUT_QUEUE
```

Your sender is producing events faster than the network (or your receiver) can consume them. Increase the queue size:

```ini
MAX_OUT_QUEUE = 500
MAX_IN_QUEUE = 1000
```

Or reduce your send rate by increasing `PYTAK_SLEEP`.

---

## FreeTAKServer: events dropped or connection refused

FTS has built-in anti-DoS rate limiting that rejects clients sending too fast. Enable compatibility mode:

```ini
FTS_COMPAT = 1
```

Or set a fixed sleep interval:

```ini
PYTAK_SLEEP = 3
```

---

## Windows-specific issues

**UDP multicast doesn't work**

Windows restricts how multicast sockets bind. Try:

- Use `udp+wo://` (write-only) instead of `udp://`
- Connect directly via `tcp://` or `tls://`

**Setting environment variables in PowerShell:**

```powershell
$env:COT_URL = "tcp://takserver.example.com:8087"
$env:DEBUG = "1"
$env:PYTAK_TLS_CLIENT_PASSWORD = "atakatak"
```

Check a variable:

```powershell
$env:COT_URL
```

---

## Still stuck?

1. Run with `DEBUG=1` and capture the full output
2. Check [open issues](https://github.com/snstac/pytak/issues) to see if it's a known problem
3. Open a new issue and include: your OS, Python version, PyTAK version, `COT_URL` (redact passwords), and the debug output
