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

    # Boilerplate: Create a Loop, create a Queue:
    loop = asyncio.get_running_loop()
    event_queue = asyncio.Queue(loop=loop)

    # CoT Event Stale period in seconds:
    cot_stale = 120

    # Define our CoT Destination URL:
    cot_url = urllib.parse.urlparse("tcp:freetakserver.example.com:8087")

    # Create our CoT Event Queue Worker
    event_worker = await pytak.eventworker_factory(cot_url, event_queue)

    # Create our Message Source (You need to implement this!)
    message_worker = MyMessageWorker(event_queue, cot_stale)

    done, pending = await asyncio.wait(
        asyncio.gather(event_worker, message_worker),
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
