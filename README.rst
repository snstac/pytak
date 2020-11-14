pytak - Python Team Awareness Kit (PyTAK) Module.
*************************************************

PyTAK is a Python Module for creating TAK clients & servers.

This module include Classes for handling CoT Events & non-CoT Messages, as well
as functions for serializing CoT Events.

Usage
=====

The following Python 3.7 code example creates a Cursor on Target Client that
gets events from a CoT Event Queue and transmits them to our destination URL
using TCP. Events are put onto the Queue by the Message Worker (QED). Events
are expected to be serialized using the ![pycot](https://github.com/ampledata/pycot)
Module::

    #!/usr/bin/env python3.7
    import asyncio
    import urllib
    import pytak

    loop = asyncio.get_running_loop()
    tx_queue: asyncio.Queue = asyncio.Queue()
    rx_queue: asyncio.Queue = asyncio.Queue()
    cot_url: urllib.parse.ParseResult = urllib.parse.urlparse('tcp:fts.example.com:8087')

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
Copyright 2020 Orion Labs, Inc.

License
=======
Apache License, Version 2.0. See LICENSE for details.
