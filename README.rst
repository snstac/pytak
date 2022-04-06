pytak - Python Team Awareness Kit (PyTAK) Module.
*************************************************
.. image:: https://raw.githubusercontent.com/ampledata/adsbxcot/main/docs/Screenshot_20201026-142037_ATAK-25p.jpg
   :alt: Screenshot of ADS-B PLI in ATAK.
   :target: https://github.com/ampledata/adsbxcot/blob/main/docs/Screenshot_20201026-142037_ATAK.jpg

**IF YOU HAVE AN URGENT OPERATIONAL NEED**: Email ops@undef.net or call/sms +1-415-598-8226

PyTAK is a Python Module for creating TAK clients & servers.

This module include Classes for handling Cursor-On-Target (COT) Events & 
non-COT Messages, as well as functions for serializing COT Events.

PyTAK has been tested with and is compatible with many SA & COP systems:

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

Support PyTAK Development
=========================

PyTAK has been developed for the Disaster Response, Public Safety and 
Frontline community at-large. This software is currently provided at no-cost 
to end-users. All development is self-funded and all time-spent is entirely
voluntary. Any contribution you can make to further these software development 
efforts, and the mission of PyTAK toprovide ongoing SA capabilities to 
end-users, is greatly appreciated:

.. image:: https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png
    :target: https://www.buymeacoffee.com/ampledata
    :alt: Support PyTAK development: Buy me a coffee!


Usage
=====

The following Python 3.7+ code example creates a Cursor-On-Target Client that
gets events from an Event Queue and transmits them to our destination URL
using TCP. Events are put onto the Queue by the Message Worker (QED). Events
are expected to be serialized XML COT::

    #!/usr/bin/env python3

    import asyncio
    import urllib
    import pytak

    cot_url = urllib.parse.urlparse('tcp:takserver.example.com:8087')

    async def main():
        # Create TX & RX queues
        tx_queue = asyncio.Queue()
        rx_queue = asyncio.Queue()

        # Create network reader & writer
        rx_proto, tx_proto = await pytak.protocol_factory(cot_url)
        
        # Create Event queue workers
        writer = pytak.EventTransmitter(tx_queue, tx_proto)
        reader = pytak.EventReceiver(rx_queue, rx_proto)

        # Create your custom Msg->COT serializer (see 'PyTAK Gateways' above)
        message_worker = MyCustomSerializer(tx_queue)

        done, pending = await asyncio.wait(
            {message_worker.run(), reader.run(), writer.run()},
            return_when=asyncio.FIRST_COMPLETED)

        for task in done:
            print(f"Task completed: {task}")



Requirements
============

PyTAK requires Python 3.6 or above and WILL NOT work on Python versions 
below 3.6 (that means no Python 2 support).


Installation
============

PyTAK is available as a Debian .deb package. This is the preferred way to 
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

    $ pip install pytak


Install PyTAK from this source tree::

    $ git clone https://github.com/ampledata/pytak.git
    $ cd pytak/
    $ python setup.py install



TLS Support
===========

TLS Support for connections to TAK destinations is configured with two 
settings:

1) Specify 'tls:' in the CoT Destination URL, for example: 'tls:takserver.example.com:8089'
2) Specify the TLS Cert & Key paramaters in the environment.

Required TLS Environment:

* PYTAK_TLS_CLIENT_CERT: TLS Public Key Certificate that the pytak client will use to connect.
* PYTAK_TLS_CLIENT_KEY: TLS Private Key for the above TLS Public Key Certificate.

Optional TLS Environment:

* PYTAK_TLS_DONT_VERIFY: Disable destination TLS Certificate Verification.
* PYTAK_TLS_DONT_CHECK_HOSTNAME: Disable destination TLS Certificate Common Name (CN) Verification.
* PYTAK_TLS_CLIENT_CAFILE: Specify CA trust store to use for remote TLS Verification.
* PYTAK_TLS_CLIENT_CIPHERS: Specify colon seperated list of TLS Cipher Suites (Defaults to FIPS 140-2 / NSA Suite B)

For example, if you're using 'adsbcot' and want to send CoT to a TAK Server
listening for TLS connections on port 8089::

    $ PYTAK_TLS_CLIENT_CERT=client.cert.pem PYTAK_TLS_CLIENT_KEY=client.key.pem \
      adsbcot -D http://172.17.2.122:8080/data/aircraft.json -U tls:takserver.example.com:8089


FreeTAKServer Support
=====================

FTS (Free TAK Server) has built-in anti-Denial-of-Service (DoS) support, which 
restricts the number of COT Events a client can send to a listening TCP Port. 
Currently this FTS feature cannot be disabled or changed, so clients must 
meter their input speed.

To use a PyTAK-based client with FTS, set the `FTS_COMPAT` Environment 
Variable to `1`. This will cause the PyTAK client to sleep a random number of 
seconds between transmitting CoT to a FTS server::

    export FTS_COMPAT=1
    aprscot ...

Or, inline::

    FTS_COMPAT=1 aprscot



Alternatively you can specify a static sleep period by setting PYTAK_SLEEP to 
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
PyTAK is Copyright 2022 Greg Albrecht

asyncio_dgram is Copyright (c) 2019 Justin Bronder


License
=======
PyTAK is licensed under the Apache License, Version 2.0. See LICENSE for details.

asyncio_dgram is licensed under the MIT License, see pytak/asyncio_dgram/LICENSE for details.


Style
=====
1. Prefer double-quotes over single quotes.
2. Prefer spaces over tabs.
3. Follow PEP-8.
4. Follow Google Python Style.
