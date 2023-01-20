.. image:: https://img.shields.io/github/sponsors/ampledata?label=Sponsor&logo=GitHub
    :alt: Support Development: Sponsor this project on GitHub sponsors.
    :target: https://github.com/sponsors/ampledata

Python Team Awareness Kit (PyTAK)
*********************************

.. image:: https://raw.githubusercontent.com/ampledata/adsbxcot/main/docs/Screenshot_20201026-142037_ATAK-25p.jpg
   :alt: Screenshot of ADS-B PLI in ATAK.
   :target: https://github.com/ampledata/adsbxcot/blob/main/docs/Screenshot_20201026-142037_ATAK.jpg


PyTAK is a Python Module for creating TAK clients, servers & gateways and includes 
classes for handling Cursor on Target (CoT) & non-CoT data, as well as functions for 
serializing CoT data, and sending and receiving CoT data over a network.

PyTAK supports the following I/O & network protocols:

* TCP Unicast: ``tcp://host:port``
* TLS Unicast: ``tls://host:port`` (see `TLS Support <https://github.com/ampledata/pytak#tls-support>`_ section below)
* UDP Unicast: ``udp://host:port``
* UDP Broadcast: ``udp+broadcast://network:port``
* UDP Multicast: ``udp://group:port``
* stdout or stderr: ``log://stdout`` or ``log://stderr``

PyTAK has been tested and is compatible with many situational awareness & common 
operating picture systems (SA & COP).

Servers:

* `TAK Server <https://tak.gov/>`_
* `taky <https://github.com/tkuester/taky>`_
* `Free TAK Server (FTS/FreeTAKServer) <https://github.com/FreeTAKTeam/FreeTakServer>`_

Clients:

* `WinTAK <https://tak.gov/>`_
* `ATAK <https://tak.gov/>`_
* `iTAK <https://tak.gov/>`_
* `TAKX <https://tak.gov/>`_
* RaptorX
* COPERS

PyTAK is used by many CoT & TAK gateways:

* `aiscot <https://github.com/ampledata/aiscot>`_: Automatic Identification System (AIS) to COT Gateway. Transforms marine AIS position messages to COT PLI Events.
* `adsbcot <https://github.com/ampledata/adsbcot>`_: Automatic Dependent Surveillance-Broadcast (ADS-B) to COT Gateway. Transforms aircraft ADS-B position messages to COT PLI Events.
* `adsbxcot <https://github.com/ampledata/adsbxcot>`_: ADS-B Exchange to COT Gateway. Transforms aircraft ADS-B position messages to COT PLI Events.
* `stratuxcot <https://github.com/ampledata/stratuxcot>`_: Stratux ADS-B to COT Gateway. Transforms aircraft ADS-B position messages to COT PLI Events.
* `aprscot <https://github.com/ampledata/aprscot>`_: Automatic Packet Reporting System (APRS) to COT Gateway. Transforms APRS position messages to COT PLI Events.
* `spotcot <https://github.com/ampledata/spotcot>`_: Globalstar SPOT to COT Gateway. Transforms Spot satellite position messages to COT PLI Events.
* `inrcot <https://github.com/ampledata/inrcot>`_: Garmin inReach to COT Gateway. Transforms inReach satellite position messages to COT PLI Events.
* `zellocot <https://github.com/ampledata/zellocot>`_: ZelloWork to COT Gateway. Transforms ZelloWork user locations to COT PLI Events.


Support Development
===================
.. image:: https://img.shields.io/github/sponsors/ampledata?label=Sponsor&logo=GitHub
    :alt: Support Development: Sponsor this project on GitHub sponsors.
    :target: https://github.com/sponsors/ampledata

.. image:: https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png
    :target: https://www.buymeacoffee.com/ampledata
    :alt: Support Development: Buy me a coffee!

.. image:: https://cdn.ko-fi.com/cdn/kofi1.png?v=3
    :target: https://ko-fi.com/T6T3D6Z9G
    :alt: Support Development: Buy Me a Coffee at ko-fi.com

**Tech Support**: Email takhelp@undef.net or `Signal <https://signal.org/>`_: +1-310-621-9598

This tool has been developed for the Disaster Response, Public Safety and
Frontline Healthcare community. This software is currently provided at no-cost
to users. Any contribution you can make to further this project's development
efforts is greatly appreciated.


Usage
=====

The following Python 3.7+ code example creates a TAK Client that generates ``takPong`` 
CoT every 20 seconds, and sends them to a TAK Server at 
``tcp://takserver.example.com:8087`` (plain / clear TCP).

* For secure TLS, see `TLS Support <https://github.com/ampledata/pytak#tls-support>`_ below. 

To run this example as-is, save the following code-block out to a file named 
``example.py`` and run the command ``python3 example.py``::

    #!/usr/bin/env python3

    import asyncio
    import xml.etree.ElementTree as ET

    from configparser import ConfigParser

    import pytak


    class MySerializer(pytak.QueueWorker):
        """
        Defines how you process or generate your Cursor-On-Target Events.
        From there it adds the COT Events to a queue for TX to a COT_URL.
        """

        async def handle_data(self, data):
            """
            Handles pre-COT data and serializes to COT Events, then puts on queue.
            """
            event = data
            await self.put_queue(event)

        async def run(self, number_of_iterations=-1):
            """
            Runs the loop for processing or generating pre-COT data.
            """
            while 1:
                data = tak_pong()
                await self.handle_data(data)
                await asyncio.sleep(20)


    def tak_pong():
        """
        Generates a simple takPong COT Event.
        """
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
        """
        The main definition of your program, sets config params and
        adds your serializer to the asyncio task list.
        """
        config = ConfigParser()
        config["mycottool"] = {"COT_URL": "tcp://takserver.example.com:8087"}
        config = config["mycottool"]

        # Initializes worker queues and tasks.
        clitool = pytak.CLITool(config)
        await clitool.setup()

        # Add your serializer to the asyncio task list.
        clitool.add_tasks(set([MySerializer(clitool.tx_queue, config)]))

        # Start all tasks.
        await clitool.run()


    if __name__ == "__main__":
        asyncio.run(main())


Requirements
============

PyTAK requires Python 3.6 or above and WILL NOT work on Python versions below 3.6. It 
should run on almost any platform that supports Python 3.6+, including Linux, Windows, 
Raspberry Pi, Android, et al.


Installation
============

PyTAK is available as a Debian ``.deb`` package. This is the preferred method to 
install PyTAK on Debian-based (Ubuntu, Debian, Raspberry Pi) systems::

    $ wget https://github.com/ampledata/pytak/releases/latest/download/python3-pytak_latest_all.deb
    $ sudo apt install -f ./python3-pytak_latest_all.deb

**N.B.** If you wish to use TAK Data Packages / Pref Packages you **must** install the 
Python cryptography module. If you're installing on a Debian-based OS::

    $ sudo apt install -y python3-cryptography

See also: https://cryptography.io/en/latest/installation/

Alternative Installation
========================

You can install from PyPI or from source. Both of these methods will require manual 
installation of additional libraries.

1a. Debian, Ubuntu, Raspberry Pi: Install `LibFFI <https://sourceware.org/libffi/>`_::

    $ sudo apt update -y
    $ sudo apt install libffi-dev

1b. RedHat, CentOS: Install `LibFFI <https://sourceware.org/libffi/>`_::

    $ sudo yum install libffi-devel

2a. Install PyTAK from the Python Package Index::

    $ python3 -m pip install pytak[with_crypto]

2b. Install PyTAK from source::

    $ git clone https://github.com/ampledata/pytak.git
    $ cd pytak/
    $ python3 setup.py install


Configuration Parameters
========================

All configuration parameters can be specified either as environment variables or 
within an INI-style configuration file.

* ``COT_URL``: (*optional*) Destination for Cursor on Target messages. Default: ``udp://239.2.3.1:6969`` (ATAK Multicast UDP Default)
* ``DEBUG``: (*optional*) Sets debug-level logging.
* ``FTS_COMPAT``: (*optional*) If set, implements random-sleep period to avoid FTS DoS protections.
* ``PYTAK_SLEEP``: (*optional*) If set, implements given sleep period between emitting CoT Events.


Data Package / Pref Package Support
===================================

PyTAK 5.5.0+ supports importing TAK Data Packages containing TAK Server connection 
settings, TLS certificates, etc. To use a .zip file with PyTAK, set the 
``PREF_PACKAGE`` config parameter to the path of the .zip file.

For example, in the ``config.ini`` file: ``PREF_PACKAGE=ADSB3_FIRE.zip``

Or on the command line: ``mycoolcotutil -p ADSB3_FIRE.zip``


TLS Support
===========

TLS Support for connections to TAK destinations is configured with two 
settings:

1) Specify ``tls://`` in the CoT Destination URL, for example: ``tls://takserver.example.com:8089``
2) Specify the TLS Cert and other configuration parameters.

Client Certificates, Client Key, CA Certificate & Key must be specified in PEM format.

*N.B*: Encrypted private keys are not supported and must be saved in clear-text: ``openssl rsa -in my_cert.key.pem -out my_cert-nopass.key.pem``

**Minimum TLS Configuration**

* ``PYTAK_TLS_CLIENT_CERT``: PEM Public Key Certificate that the PyTAK-based client will use to connect.

**Optional TLS Configuration**

* ``PYTAK_TLS_CLIENT_KEY``: PEM Private Key for the associated ``PYTAK_TLS_CLIENT_CERT``
* ``PYTAK_TLS_DONT_VERIFY``: Disable destination TLS Certificate Verification.
* ``PYTAK_TLS_DONT_CHECK_HOSTNAME``: Disable destination TLS Certificate Common Name (CN) Verification.
* ``PYTAK_TLS_CLIENT_CAFILE``: PEM CA trust store to use for remote TLS Verification.
* ``PYTAK_TLS_CLIENT_CIPHERS``: Colon (":") seperated list of TLS Cipher Suites.

For example, to send COT to a TAK Server listening for TLS connections on port 
8089::

    PYTAK_TLS_CLIENT_CERT=client.cert.pem 
    PYTAK_TLS_CLIENT_KEY=client.key.pem
    COT_URL=tls://tak.example.com:8089


FreeTAKServer Support
=====================

FTS (Free TAK Server) has built-in anti-Denial-of-Service (DoS) support, which 
restricts the number of CoT Events a client can send to a listening TCP Port. 
Currently this FTS feature cannot be disabled or changed, so clients must meter 
their input speed.

To use a PyTAK-based client with FTS, set the ``FTS_COMPAT`` configuration parameter 
to ``True``. This will cause the PyTAK client to sleep a random number of seconds 
between transmitting CoT to a FTS server::

    FTS_COMPAT = True

Alternatively you can specify a static sleep period by setting ``PYTAK_SLEEP`` to an 
integer number of seconds::

    PYTAK_SLEEP = 3


TAK Protocol Payload - Version 1 (Protobuf) Support
===================================================

    Version 1 of the TAK Protocol Payload is a Google Protocol Buffer based
    payload.  Each Payload consists of one (and only one)
    atakmap::commoncommo::v1::TakMessage message which is serialized using
    Google protocol buffers version 3.

    Source: https://github.com/deptofdefense/AndroidTacticalAssaultKit-CIV/blob/master/commoncommo/core/impl/protobuf/protocol.txt

PyTAK natively sends and receives "TAK Protocol Payload - Version 0", aka plain XML. If 
you'd like to receive & decode "Version 1" protobuf with PyTAK, install the 
`takproto <https://github.com/ampledata/takproto>`_ Python module::

    $ python3 -m pip install takproto

Here is an example of receiving & decoding "Version 1" using ``takproto``. 

N.B. The data type returned from this implementation differs from that of the 
"Version 0" implementation (``bytes`` vs ``object``)::

    #!/usr/bin/env python3

    import asyncio

    from configparser import ConfigParser

    import takproto

    import pytak


    class MyRXWorker(pytak.RXWorker):
        async def readcot(self):
            if hasattr(self.reader, 'readuntil'):
                cot = await self.reader.readuntil("</event>".encode("UTF-8"))
            elif hasattr(self.reader, 'recv'):
                cot, src = await self.reader.recv()
            tak_v1 = takproto.parse_proto(cot)
            if tak_v1 != -1:
                cot = tak_v1
            return cot


    async def my_setup(clitool) -> None:
        reader, writer = await pytak.protocol_factory(clitool.config)
        write_worker = pytak.TXWorker(clitool.tx_queue, clitool.config, writer)
        read_worker = MyRXWorker(clitool.rx_queue, clitool.config, reader)
        clitool.add_task(write_worker)
        clitool.add_task(read_worker)


    async def main():
        """
        The main definition of your program, sets config params and
        adds your serializer to the asyncio task list.
        """
        config = ConfigParser()
        config["mycottool"] = {"COT_URL": "udp://239.2.3.1:6969"}
        config = config["mycottool"]

        # Initializes worker queues and tasks.
        clitool = pytak.CLITool(config)
        await my_setup(clitool)

        # Start all tasks.
        await clitool.run()


    if __name__ == "__main__":
        asyncio.run(main())



Source
======
Github: https://github.com/ampledata/pytak


Author
======
Greg Albrecht W2GMD oss@undef.net

https://ampledata.org/


Copyright
=========

* PyTAK is Copyright 2023 Greg Albrecht
* asyncio_dgram is Copyright (c) 2019 Justin Bronder


License
=======

Copyright 2023 Greg Albrecht <oss@undef.net>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

* asyncio_dgram is licensed under the MIT License, see pytak/asyncio_dgram/LICENSE for details.


Style
=====
Python Black, otherwise Google, then PEP-8.