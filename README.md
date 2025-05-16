![ATAK Screenshot with PyTAK Logo.](https://pytak.readthedocs.io/en/stable/media/atak_screenshot_with_pytak_logo-x25.jpg)

# Python Team Awareness Kit

PyTAK is a Python Module for creating Team Awareness Kit ([TAK](https://tak.gov)) clients, servers & gateways.

## Features

- **TAK Protocol Support**: Connect with ATAK, WinTAK, iTAK, and TAK Server.
- **Data Handling**: Manage TAK, Cursor on Target (CoT), and non-CoT data.
- **Data Parsing and Serialization**: Parse and serialize TAK and CoT data.
- **Network Communication**: Send and receive TAK and CoT data over a network.
- **COT Building Support**: Build your COTs fast and easy by leveraging easy-to-use builder functions.

## Documentation

See [PyTAK documentation](https://pytak.rtfd.io/) for instructions on getting
started with PyTAK, examples, configuration & troubleshooting options.

## COT Building

This library provides the following functions to help the user build COTs:

- `gen_cot_xml(...)`: generates a minimum COT event in XML and returns it as `ET.Element` object. This object can be modified later by adding or editing its elements.
- `gen_cot_detailed_xml(...)`: generates a more detailed COT event in XML with support for all attributes for the `event` element. Returns COT as `ET.Element` object. This object can be modified later by adding or editing its elements.
- `gen_cot(...)`: a wrapper function around `gen_cot_xml(...)`. Returns COT as `bytes` and is ready to send to TAK server. This is the way to go if you are looking for easy and fast integration of your COTs, or you are not interested in modifying the COTs any further.
- `gen_delete_cot_xml(uid_to_delete, ...)`: generates a COT that will delete a previous sent COT if it matches the `uid`. Returns COT as `bytes` and is ready to be sent to TAK without having to make any change to it.

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
