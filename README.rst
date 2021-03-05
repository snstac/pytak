pytak - Python Team Awareness Kit (PyTAK) Module.
*************************************************

PyTAK is a Python Module for creating TAK clients & servers.

This module include Classes for handling CoT Events & non-CoT Messages, as well
as functions for serializing CoT Events. As a bonus, there are helper functions
for classifying Aircraft attitude/affiliation/posture based on ICAO, Emitter
Category, Flight Name, et al.

**IF YOU HAVE AN URGENT OPERATIONAL NEED**: Email ops@undef.net or call/sms +1-415-598-8226

Examples of TAK Clients using the this module:

* `aiscot <https://github.com/ampledata/aiscot>`_: Automatic Identification System (AIS) to Cursor on Target (CoT) Gateway. Transforms AIS position messages to CoT PLI Events.
* `adsbcot <https://github.com/ampledata/adsbcot>`_: Automatic Dependent Surveillance-Broadcast (ADS-B) to Cursor on Target (CoT) Gateway. Transforms ADS-B position messages to CoT PLI Events.
* `adsbxcot <https://github.com/ampledata/adsbxcot>`_: ADS-B Exchange to Cursor on Target (CoT) Gateway. Transforms ADS-B position messages to CoT PLI Events.
* `stratuxcot <https://github.com/ampledata/stratuxcot>`_: Stratux ADS-B to Cursor on Target (CoT) Gateway. Transforms position messages to CoT PLI Events.
* `aprscot <https://github.com/ampledata/aprscot>`_: Automatic Packet Reporting System (APRS) to Cursor on Target (CoT) Gateway. Transforms APRS position messages to CoT PLI Events.

See also:

* `pycot <https://github.com/ampledata/pycot>`_: Python Cursor on Target (CoT), a Python Module for serializing CoT Events, for use with TAK clients & servers.

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

PyTAK requires the FFI Library libffi (or libffi-dev), to install follow these
instructions.

Debian & Ubuntu::

  $ sudo apt-get install libffi-dev

RedHat, Fedora, CentOS::

  $ sudo yum install libffi-devel
  # or
  $ sudo dnf install libffi-devel


Installation
============

Option A) Install from the Python Package Index::

    $ pip install pytak


Option B) Install from this source tree::

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

Build Status
============

.. image:: https://travis-ci.com/ampledata/pytak.svg?branch=main
    :target: https://travis-ci.com/ampledata/pytak

Source
======
Github: https://github.com/ampledata/pytak

Author
======
Greg Albrecht W2GMD oss@undef.net

https://www.orionlabs.io/

Copyright
=========
Copyright 2021 Orion Labs, Inc.

License
=======
Apache License, Version 2.0. See LICENSE for details.

Style
=====

1. Prefer double-quotes over single quotes.
2. Prefer spaces over tabs.
3. Follow PEP-8.
4. Follow Google Python Style.
