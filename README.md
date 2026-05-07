<img src="https://raw.githubusercontent.com/snstac/pytak/main/docs/media/pytak_logo.png" alt="PyTAK Logo" width="200">

# Python Team Awareness Kit (PyTAK)

PyTAK is a Python library for building [TAK](https://tak.gov) clients, servers & gateways — things that send and receive Cursor on Target (CoT) data on TAK networks.

## Install

```sh
python3 -m pip install pytak
```

## Quick example

```python
import asyncio, xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak

class MySender(pytak.QueueWorker):
    async def handle_data(self, data):
        await self.put_queue(data)
    async def run(self):
        while True:
            root = ET.Element("event", version="2.0", type="t-x-d-d",
                              uid="myMarker", how="m-g",
                              time=pytak.cot_time(), start=pytak.cot_time(),
                              stale=pytak.cot_time(3600))
            await self.handle_data(ET.tostring(root))
            await asyncio.sleep(20)

async def main():
    config = ConfigParser()
    config["mytool"] = {"COT_URL": "tcp://takserver.example.com:8087"}
    config = config["mytool"]
    clitool = pytak.CLITool(config)
    await clitool.setup()
    clitool.add_tasks(set([MySender(clitool.tx_queue, config)]))
    await clitool.run()

asyncio.run(main())
```

## Features

- **TAK Protocol support** — XML (TAK Protocol v0) and Protobuf (TAK Protocol v1, via `takproto`)
- **Multiple transports** — TCP, TLS, UDP unicast, UDP multicast (Mesh SA), UDP broadcast, file, stdout
- **TLS client auth** — PEM certs, PKCS#12 (`.p12`), password-protected keys
- **TAK enrollment** — automatic certificate enrollment from a `tak://` onboarding URL
- **Marti REST API** — send/receive CoT via TAK Server's HTTP API (`marti://` URL scheme)
- **TAK Data Packages** — import `.zip` pref packages containing server connection settings and certs
- **FreeTAKServer compat** — built-in rate-limiting mode (`FTS_COMPAT`)
- **No required external deps** — pure-Python asyncio core; optional extras for TLS enrollment and Protobuf

## Documentation

Full documentation at **[pytak.rtfd.io](https://pytak.rtfd.io/)** including installation, configuration, examples, and troubleshooting.

## License & Copyright

Copyright Sensors & Signals LLC https://www.snstac.com

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

asyncio_dgram is Copyright (c) 2019 Justin Bronder and is licensed under the MIT
License, see pytak/asyncio_dgram/LICENSE for details.
