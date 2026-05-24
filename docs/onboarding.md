# Onboarding data packages (`pytak dp`)

Enroll a TAK user from an ATAK enrollment deep-link and produce PKCS#12/PEM files plus **ATAK** and **iTAK** connection data packages — without connecting to the CoT network.

!!! note "vs `pytak tak://...`"
    `pytak tak://...` enrolls into `~/.pytak/certs/` and **connects** to the server (WebSocket/Marti).  
    `pytak dp` enrolls into an output folder and **only writes files** for device import.

## Requirements

```bash
python3 -m pip install pytak[with-aiohttp,with-crypto]
```

## Usage

```bash
pytak dp 'tak://com.atakmap.app/enroll?host=takserver.example.com&username=myuser&token=SECRET'
```

Optional flags:

| Flag | Description |
|------|-------------|
| `-o DIR` | Parent output directory (default: `data-packages`) |
| `--package-stem NAME` | Subfolder and file prefix (default: sanitized username) |
| `--streaming-host HOST` | Hostname in CoT `connectString` (default: `host` from URL) |
| `--streaming-port PORT` | Streaming port (default: `8089`) |
| `--dp-callsign CALLSIGN` | `locationCallsign` in package prefs |
| `-v` | Verbose logging and PKCS#12 password on stderr |

Progress goes to **stderr**; resulting paths are printed on **stdout** as `key=value` lines.

## Output layout

For username `myuser` and default stem:

```
data-packages/myuser/
  certs/
    myuser.p12          # client identity (key + cert + CA chain)
    myuser.pem          # client certificate PEM
    myuser-key.pem      # private key PEM
    myuser-ca.pem       # CA chain PEM
    myuser-trust.p12    # CA-only trust store (for data packages)
  myuser-atak-connection.zip
  myuser-itak-connection.zip
```

Import the ATAK ZIP into ATAK (or CivTAK) and the iTAK ZIP into iTAK. PKCS#12 passwords for both bundles inside the ZIP are the same; use `-v` to print the generated password.

## Programmatic use

```python
import asyncio
from pytak.onboarding_packages import enroll_onboarding_package

result = asyncio.run(
    enroll_onboarding_package(
        "tak://com.atakmap.app/enroll?host=takserver.example.com&username=u&token=t",
        "data-packages",
    )
)
print(result["data_package_zip"])
```
