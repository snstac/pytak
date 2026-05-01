# Quick Start

Get CoT events on the TAK network in under 5 minutes.

## 1. Install PyTAK

=== "pip (recommended)"
    ```sh
    python3 -m pip install pytak
    ```

=== "Debian / Ubuntu / Raspberry Pi"
    ```sh
    sudo apt update -qq
    wget https://github.com/snstac/pytak/releases/latest/download/pytak_latest_all.deb
    sudo apt install -f ./pytak_latest_all.deb
    ```

See [Installation](installation.md) for more options.

## 2. Write your first sender

Save this as `send.py`. It sends a `takPong` marker to a TAK Server every 20 seconds over plain TCP.

```python
#!/usr/bin/env python3
import asyncio
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak


class MySender(pytak.QueueWorker):
    async def handle_data(self, data):
        await self.put_queue(data)

    async def run(self):
        while True:
            await self.handle_data(tak_pong())
            await asyncio.sleep(20)


def tak_pong():
    root = ET.Element("event")
    root.set("version", "2.0")
    root.set("type", "t-x-d-d")
    root.set("uid", "takPong")
    root.set("how", "m-g")
    root.set("time", pytak.cot_time())
    root.set("start", pytak.cot_time())
    root.set("stale", pytak.cot_time(3600))
    return ET.tostring(root)


async def main():
    config = ConfigParser()
    config["mytool"] = {"COT_URL": "tcp://takserver.example.com:8087"}
    config = config["mytool"]

    clitool = pytak.CLITool(config)
    await clitool.setup()
    clitool.add_tasks(set([MySender(clitool.tx_queue, config)]))
    await clitool.run()


if __name__ == "__main__":
    asyncio.run(main())
```

## 3. Run it

```sh
python3 send.py
```

Change the `COT_URL` to match your TAK Server address and port. See [Configuration](configuration.md) for all URL formats including TLS, UDP multicast, and more.

---

## Common connection patterns

| Network | `COT_URL` example |
|---|---|
| TAK Server TCP | `tcp://takserver.example.com:8087` |
| TAK Server TLS | `tls://takserver.example.com:8089` |
| ATAK direct (phone) | `tcp://192.168.1.50:4242` |
| Mesh SA (multicast) | `udp://239.2.3.1:6969` |
| Debug to console | `log://stdout` |

---

## Next steps

- **TLS connection** — see [Examples: TLS Send](examples.md#tls-send)
- **Receive CoT** — see [Examples: Send & Receive](examples.md#send-receive-tak-data)
- **TAK enrollment URL** — see [Configuration: tak:// URL](configuration.md#tak-onboarding-url)
- **All config options** — see [Configuration](configuration.md)
- **Something not working?** — see [Troubleshooting](troubleshooting.md)
