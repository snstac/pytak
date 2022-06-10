pytak - Python Team Awareness Kit (PyTAK) Module.
*************************************************
.. image:: https://raw.githubusercontent.com/ampledata/adsbxcot/main/docs/Screenshot_20201026-142037_ATAK-25p.jpg
   :alt: Screenshot of ADS-B PLI in ATAK.
   :target: https://github.com/ampledata/adsbxcot/blob/main/docs/Screenshot_20201026-142037_ATAK.jpg


PyTAK is a Python Module for creating TAK clients, servers & gateways and include 
classes for handling Cursor-On-Target (COT) Events & non-COT Messages, as well 
as functions for serializing COT Events.

PyTAK supports the following network protocols:

* TCP Unicast: ``tcp://host:port``
* TLS Unicast: ``tls://host:port`` (see 'TLS Support' section below)
* UDP Unicast: ``udp://host:port``
* UDP Broadcast: ``udp+broadcast://network:port``
* UDP Mulicast: ``udp://group:port``
* STDOUT/STDERR: ``log://stdout`` or ``log://stderr``

PyTAK has been tested and is compatible with many SA & COP systems.

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

PyTAK is used by many COT gateways:

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

**Tech Support**: Email support@undef.net or Signal/WhatsApp: +1-310-621-9598

This tool has been developed for the Disaster Response, Public Safety and
Frontline Healthcare community. This software is currently provided at no-cost
to users. Any contribution you can make to further this project's development
efforts is greatly appreciated.

.. image:: https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png
    :target: https://www.buymeacoffee.com/ampledata
    :alt: Support Development: Buy me a coffee!


Usage
=====

The following Python 3.7+ code example creates a Cursor-On-Target Client that
gets events from an Event Queue and transmits them to our destination URL
using TCP. Events are put onto the Queue by the Message Worker (QED). Events
are expected to be serialized XML COT::

    #!/usr/bin/env python3
    
    import asyncio
    from configparser import ConfigParser
    import pytak

    class MyWorker(pytak.QueueWorker):
        async def run(self):
            while 1:
                await self.read_queue()

    config = ConfigParser()["DEFAULT"]
    config.set("COT_URL", "tcp://takserver.example.com:8087")

    clitool = pytak.CLITool(config)
    await clitool.setup()

    # Create your custom Msg->COT serializer:
    clitool.add_tasks(set([MyCustomSerializer(clitool.tx_queue, config)]))

    await clitool.run()


Requirements
============

PyTAK requires Python 3.6 or above and WILL NOT work on Python versions 
below 3.6 (that means no Python 2 support).


Installation
============

PyTAK is available as a Debian ``.deb`` package. This is the preferred way to 
install PyTAK as it will pull in all of the required OS-level dependencies::

    $ wget https://github.com/ampledata/pytak/releases/latest/download/python3-pytak_latest_all.deb
    $ sudo apt install -f ./python3-pytak_latest_all.deb


Alternative Installation
========================

You can install from PyPI or from source. Both of these methods will require 
additional OS libraries.

Install LibFFI on Ubuntu::

  $ sudo apt-get install libffi-dev

Install LibFFI on RedHat, Fedora, CentOS::

  $ sudo yum install libffi-devel
  # or
  $ sudo dnf install libffi-devel


Install PyTAK from the Python Package Index::

    $ python3 -m pip install pytak


Install PyTAK from this source tree::

    $ git clone https://github.com/ampledata/pytak.git
    $ cd pytak/
    $ python3 setup.py install


Configuration Parameters
========================

All configuration parameters can be specified either as environment variables or 
within an INI-style configuration file.

* ``COT_URL``: (*optional*) Destination for Cursor-On-Target messages. Default: ``udp://239.2.3.1:6969`` (ATAK Multicast UDP Default)
* ``DEBUG``: (*optional*) Sets debug-level logging.
* ``FTS_COMPAT``: (*optional*) If set, implements random-sleep period to avoid FTS DoS protections.
* ``PYTAK_SLEEP``: (*optional*) If set, implements given sleep period between emitting COT Events.


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

For example, if you're using 'adsbxcot' and want to send CoT to a TAK Server
listening for TLS connections on port 8089, specifying configuration parameters 
as environment variables::

    $ export PYTAK_TLS_CLIENT_CERT=client.cert.pem 
    $ export PYTAK_TLS_CLIENT_KEY=client.key.pem
    $ export COT_URL=tls://tak.example.com:8089
    $ adsbxcot


FreeTAKServer Support
=====================

FTS (Free TAK Server) has built-in anti-Denial-of-Service (DoS) support, which 
restricts the number of COT Events a client can send to a listening TCP Port. 
Currently this FTS feature cannot be disabled or changed, so clients must 
meter their input speed.

To use a PyTAK-based client with FTS, set the ``FTS_COMPAT`` Environment 
Variable to ``1``. This will cause the PyTAK client to sleep a random number of 
seconds between transmitting CoT to a FTS server::

    export FTS_COMPAT=1
    aprscot ...

Or, inline::

    FTS_COMPAT=1 aprscot


Alternatively you can specify a static sleep period by setting ``PYTAK_SLEEP`` to 
an integer number of seconds::

    export PYTAK_SLEEP=3
    spotcot ...


Source
======
Github: https://github.com/ampledata/pytak


Author
======
Greg Albrecht W2GMD oss@undef.net

https://ampledata.org/


Copyright
=========

* PyTAK is Copyright 2022 Greg Albrecht
* asyncio_dgram is Copyright (c) 2019 Justin Bronder


License
=======

Copyright 2022 Greg Albrecht <oss@undef.net>

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
1. Prefer double-quotes over single quotes.
2. Prefer spaces over tabs.
3. Follow PEP-8.
4. Follow Google Python Style.
