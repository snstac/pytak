# Examples

## Send TAK Data

Send a `takPong` CoT marker every 20 seconds over plain TCP. Save as `send.py` and run with `python3 send.py`.

```python
{!examples/send.py!}
```

---

## Build CoT For Child Clients

PyTAK-based gateways such as ADSBCOT, AISCOT, DRONECOT, LINCOT, and DHBridge
should use the shared CoT helpers for standard event metadata, point formatting,
flow tags, remarks, and serialization. Keep sensor-specific detail elements in
the child client, but let PyTAK own the common CoT skeleton.

```python
import xml.etree.ElementTree as ET

import pytak


track = ET.Element("track")
track.set("course", "90")
track.set("speed", "12.3")

detail = pytak.cot_detail(track)
pytak.add_remarks(
    detail,
    [
        "Remote ID: uas-123",
        "Sensor: aryaos-39e7",
        f"TAK: {pytak.sanitize_url_credentials('tls://user:pass@tak.example:8089')}",
    ],
)

event = pytak.cot_event(
    lat=37.760050100,
    lon=-122.497702900,
    hae=10,
    ce=5,
    le=8,
    uid="UAS.uas-123",
    cot_type="a-f-A-M-F-Q",
    stale=60,
    detail=detail,
    callsign="uas-123",
)

payload = pytak.serialize_cot(event, trailing_newline=True)
```

`cot_point()` and `cot_event()` truncate latitude and longitude to at most four
decimal places by default. This is intentional for TAK client compatibility.

---

## Send & Receive TAK Data {#send-receive-tak-data}

Send a position marker every 5 seconds **and** receive all incoming CoT from the same TCP connection. Received events are logged to console.

Save as `send_receive.py` and run with `python3 send_receive.py`.

```python
{!examples/send_receive.py!}
```

Key differences from the send-only example:

- `MySender` uses `clitool.tx_queue` — events go to the network
- `MyReceiver` uses `clitool.rx_queue` — events come from the network
- Both workers are added to the task set so they run concurrently

---

## TLS Send {#tls-send}

Connect to a TAK Server over TLS using a client certificate and key. This is the standard connection method for production TAK Server deployments.

Generate a client cert on the TAK Server first:

```sh
sudo /opt/tak/certs/makeCert.sh client myclient
```

This produces `myclient.pem` and `myclient.key`. Copy them to your client machine, then:

```python
{!examples/tls_send.py!}
```

!!! tip "Certificate password"
    TAK Server's `makeCert.sh` creates password-protected keys. The default password is set in `CoreConfig.xml` (typically `atakatak`). Set it via `PYTAK_TLS_CLIENT_PASSWORD`.

!!! warning "PYTAK_TLS_DONT_VERIFY in production"
    `PYTAK_TLS_DONT_VERIFY = True` skips server cert validation. This is shown for development convenience; in production, provide `PYTAK_TLS_CLIENT_CAFILE` pointing to your TAK Server's CA chain instead.

---

## TLS Send with Certificate Enrollment {#tls-send-with-enrollment}

Automatically enroll a client certificate from a TAK Server using your TAK account credentials. PyTAK handles the full CSR → PKCS#12 flow and caches the certificate locally.

Requires `pip install pytak[with_aiohttp,with_crypto]`.

```python
{!examples/tls_send_with_enrollment.py!}
```

After the first run, the enrolled certificate is cached in `~/.pytak/certs/` and reused on subsequent runs (re-enrollment happens automatically when the cert is within 7 days of expiry).

---

## TAK Enrollment URL

If your TAK admin provided a `tak://` onboarding URL (e.g. via QR code), pass it directly as `COT_URL`. PyTAK handles enrollment and TLS setup automatically.

Command-line usage:

```sh
pytak "tak://com.atakmap.app/enroll?host=takserver.example.com&username=myuser&token=mytoken"
```

If you need to force a specific WebSocket/Marti port, include it in `host=`:

```sh
pytak "tak://com.atakmap.app/enroll?host=takserver.example.com:8443&username=myuser&token=mytoken"
```

```python
import asyncio
from configparser import ConfigParser
import pytak


class MySender(pytak.QueueWorker):
    async def handle_data(self, data):
        await self.put_queue(data)

    async def run(self):
        import xml.etree.ElementTree as ET
        while True:
            root = ET.Element("event", version="2.0", type="t-x-d-d",
                              uid="myMarker", how="m-g",
                              time=pytak.cot_time(), start=pytak.cot_time(),
                              stale=pytak.cot_time(3600))
            await self.handle_data(ET.tostring(root))
            await asyncio.sleep(20)


async def main():
    config = ConfigParser()
    config["mytool"] = {
        # Paste your tak:// URL here
        "COT_URL": "tak://com.atakmap.app/enroll?host=takserver.example.com&username=myuser&token=mytoken",
    }
    config = config["mytool"]

    clitool = pytak.CLITool(config)
    await clitool.setup()
    clitool.add_tasks(set([MySender(clitool.tx_queue, config)]))
    await clitool.run()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Marti REST API

Send and receive CoT via the TAK Server's Marti HTTP API instead of a raw TCP/TLS socket. Useful when firewall rules block direct streaming ports.

Requires `pip install pytak[with_aiohttp]`.

```python
import asyncio
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak


class MySender(pytak.QueueWorker):
    async def handle_data(self, data):
        await self.put_queue(data)

    async def run(self):
        while True:
            root = ET.Element("event", version="2.0", type="t-x-d-d",
                              uid="martiMarker", how="m-g",
                              time=pytak.cot_time(), start=pytak.cot_time(),
                              stale=pytak.cot_time(3600))
            await self.handle_data(ET.tostring(root))
            await asyncio.sleep(10)


async def main():
    config = ConfigParser()
    config["mytool"] = {
        "COT_URL": "marti://takserver.example.com:8443",
        # Optional: provide client cert for mTLS
        # "PYTAK_TLS_CLIENT_CERT": "/etc/pytak/client.pem",
    }
    config = config["mytool"]

    clitool = pytak.CLITool(config)
    await clitool.setup()
    clitool.add_tasks(set([MySender(clitool.tx_queue, config)]))
    await clitool.run()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## MQTT broker

Publish and receive CoT on the same MQTT topic. Requires `pytak[with-mqtt]`:

```sh
pip install pytak[with-mqtt]
```

```python
#!/usr/bin/env python3
import asyncio
from configparser import ConfigParser

import pytak


class MySender(pytak.QueueWorker):
    async def handle_data(self, data):
        event = pytak.SimpleCOTEvent(
            lat=37.7749, lon=-122.4194, uid="MQTT-TEST", stale=60
        )
        await self.put_queue(event.cot2xml())


async def main():
    config = ConfigParser()
    config["mytool"] = {
        "COT_URL": "mqtt://broker.example.com:1883/cot",
        "TAK_PROTO": "0",
    }
    config = config["mytool"]

    clitool = pytak.CLITool(config)
    await clitool.setup()
    clitool.add_tasks(set([MySender(clitool.tx_queue, config)]))
    await clitool.run()


if __name__ == "__main__":
    asyncio.run(main())
```

For publish-only gateways, use `mqtt+wo://broker.example.com:1883/cot`.

---

## Send-only to a TAK Server

If your tool only publishes CoT and does not process inbound events (for example, a sensor gateway), use the `+wo` modifier so PyTAK does not enqueue received data:

```ini
COT_URL = tls+wo://takserver.example.com:8089
```

---

## Debug: Print CoT to Console

Use `log://stdout` as the `COT_URL` to print CoT XML to your console without a network connection. Useful for verifying your CoT format before connecting to a real server.

```ini
COT_URL = log://stdout
```

Or in Python:

```python
config["mytool"] = {"COT_URL": "log://stdout"}
```
