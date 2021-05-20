pytak - Python Team Awareness Kit (PyTAK) Module.
*************************************************
**IF YOU HAVE AN URGENT OPERATIONAL NEED**: Email ops@undef.net or call/sms +1-415-598-8226

PyTAK is a Python Module for creating TAK clients & servers.

This module include Classes for handling CoT Events & non-CoT Messages, as well
as functions for serializing CoT Events. As a bonus, there are helper functions
for classifying Aircraft attitude/affiliation/posture based on ICAO, Emitter
Category, Flight Name, et al.

PyTAK has been tested with and is compatible with the following:

Servers:

* `TAK Server <https://takmaps.com/>`_
* `Free TAK Server (FTS/FreeTAKServer) <https://github.com/FreeTAKTeam/FreeTakServer>`_
* `taky <https://github.com/tkuester/taky>`_
* `PAR Team Connect <https://pargovernment.com/TeamConnect/>`_ **COMMING SOON**

Clients:

* `WinTAK <https://www.civtak.org/2020/09/23/wintak-is-publicly-available/>`_
* `ATAK <https://www.civtak.org/download-atak/>`_
* `RedTAK <http://ampledata.org/node_red_atak.html>`_
* RaptorX
* `WebTAK <https://takmaps.com/>`_ **NOT CURRENTLY WORKING**

Examples of software clients using the the PyTAK Python Module include:

* `aiscot <https://github.com/ampledata/aiscot>`_: Automatic Identification System (AIS) to Cursor on Target (CoT) Gateway. Transforms AIS position messages to CoT PLI Events.
* `adsbcot <https://github.com/ampledata/adsbcot>`_: Automatic Dependent Surveillance-Broadcast (ADS-B) to Cursor on Target (CoT) Gateway. Transforms ADS-B position messages to CoT PLI Events.
* `adsbxcot <https://github.com/ampledata/adsbxcot>`_: ADS-B Exchange to Cursor on Target (CoT) Gateway. Transforms ADS-B position messages to CoT PLI Events.
* `stratuxcot <https://github.com/ampledata/stratuxcot>`_: Stratux ADS-B to Cursor on Target (CoT) Gateway. Transforms position messages to CoT PLI Events.
* `aprscot <https://github.com/ampledata/aprscot>`_: Automatic Packet Reporting System (APRS) to Cursor on Target (CoT) Gateway. Transforms APRS position messages to CoT PLI Events.
* `spotcot <https://github.com/ampledata/spotcot>`_: Globalstar SPOT to Cursor on Target (CoT) Gateway. Transforms Spot position messages to CoT PLI Events.


Support PyTAK Development
=========================

PyTAK has been developed for the Disaster Response, Public Safety and Frontline community at-large. This software is
currently provided at no-cost to our end-users. All development is self-funded and all time-spent is entirely
voluntary. Any contribution you can make to further these software development efforts, and the mission of PyTAK to
provide ongoing SA capabilities to our end-users, is greatly appreciated:

.. image:: https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png
    :target: https://www.buymeacoffee.com/ampledata
    :alt: Support PyTAK development: Buy me a coffee!

Usage
=====

The following Python 3.7 code example creates a Cursor on Target Client that
gets events from a CoT Event Queue and transmits them to our destination URL
using TCP. Events are put onto the Queue by the Message Worker (QED). Events
are expected to be serialized using the `pycot <https://github.com/ampledata/pycot>`_
Module::

    #!/usr/bin/env python3.7

    import asyncio
    import urllib
    import pytak

    loop = asyncio.get_running_loop()
    tx_queue: asyncio.Queue = asyncio.Queue()
    rx_queue: asyncio.Queue = asyncio.Queue()
    cot_url: urllib.parse.ParseResult = urllib.parse.urlparse("tcp:fts.example.com:8087")

    # Create our CoT Event Queue Worker
    reader, writer = await pytak.protocol_factory(cot_url)
    write_worker = pytak.EventTransmitter(tx_queue, writer)
    read_worker = pytak.EventReceiver(rx_queue, reader)

    message_worker = MyMessageWorker(
        event_queue=tx_queue,
        cot_stale=opts.cot_stale
    )

    done, pending = await asyncio.wait(
        set([message_worker.run(), read_worker.run(), write_worker.run()]),
        return_when=asyncio.FIRST_COMPLETED)

    for task in done:
        print(f"Task completed: {task}")



Requirements
============

PyTAK requires Python 3.6 or above and WILL NOT work on Python versions below 3.6 (that means no Python 2 support).

Installation
============

New for 2021, PyTAK is available as a Debian .deb package. This is the preferred way to install PyTAK as it will pull
in all of the required OS-level dependencies::

    $ wget https://github.com/ampledata/pytak/releases/latest/download/python3-pytak_latest_all.deb
    $ sudo apt install -f ./python3-pytak_latest_all.deb

Alternative Installation
========================

(you should really install from an OS package above!)

You can install from PyPI or from source. Both of these methods will require additional OS libraries:

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

TLS Support for connections to TAK destinations is configured with two settings:

1) Specify 'tls:' in the CoT Destination URL, for example: 'tls:my-tak-server.example.com:8089'
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
      adsbcot -D http://172.17.2.122:8080/data/aircraft.json -U tls:my-tak-server.example.com:8089


FreeTAKServer Support
=====================

FTS (Free TAK Server) has built-in anti-Denial-of-Service (DoS) support, which restricts the number of CoT Events a
client can send to a listening TCP Port. Currently this FTS feature cannot be disabled or changed, so clients must
meter their input speed.

To use a PyTAK-based client with FTS, set the `FTS_COMPAT` Environment Variable to `1`. This will cause the PyTAK
client to sleep a random number of seconds between transmitting CoT to a FTS server::

    export FTS_COMPAT=1
    aprscot ...

Or, inline::

    FTS_COMPAT=1 aprscot



Alternatively you can specify a static sleep period by setting PYTAK_SLEEP to an integer number of seconds::

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
PyTAK is Copyright 2021 Orion Labs, Inc.

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
