Compatibility
=============

Clients & Servers
-----------------
PyTAK is used in mission criticial environments, every day, across all official 
`TAK Products <https://tak.gov>`_:

* `WinTAK <https://tak.gov/>`_
* `ATAK <https://tak.gov/>`_
* `iTAK <https://tak.gov/>`_
* `TAKX <https://tak.gov/>`_
* `TAK Server <https://tak.gov/>`_

PyTAK has been tested and is compatible with many situational awareness (SA) & common 
operating picture (COP) systems:

* `taky <https://github.com/tkuester/taky>`_
* `Free TAK Server (FTS/FreeTAKServer) <https://github.com/FreeTAKTeam/FreeTakServer>`_
* RaptorX
* COPERS

I/O & Network Protocols
-----------------------
PyTAK supports the following I/O & network protocols:

* TLS Unicast: ``tls://host:port`` (see `TLS Support <https://github.com/snstac/pytak#tls-support>`_ section below)
* TCP Unicast: ``tcp://host:port``
* UDP Multicast: ``udp://group:port`` (aka Mesh SA)
* UDP Unicast: ``udp://host:port``
* UDP Broadcast: ``udp+broadcast://network:port``
* UDP Write-only: ``udp+wo://host:port``
* stdout or stderr: ``log://stdout`` or ``log://stderr``

Python 3.6+
-----------

PyTAK requires Python 3.6 or above and WILL NOT work on Python versions below 3.6. It 
should run on almost any platform that supports Python 3.6+, including Linux, Windows, 
Raspberry Pi, Android, et al.


FreeTAKServer
-------------

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


TAK Protocol Payload - Version 1 (Protobuf)
-------------------------------------------

    Version 1 of the TAK Protocol Payload is a Google Protocol Buffer based
    payload.  Each Payload consists of one (and only one)
    atakmap::commoncommo::v1::TakMessage message which is serialized using
    Google protocol buffers version 3.

    Source: https://github.com/deptofdefense/AndroidTacticalAssaultKit-CIV/blob/master/commoncommo/core/impl/protobuf/protocol.txt

PyTAK natively sends and receives "TAK Protocol Payload - Version 0", aka plain XML. If 
you'd like to receive & decode "Version 1" protobuf with PyTAK, install the optional 
`takproto <https://github.com/snstac/takproto>`_ Python module::

When installing PyTAK::

    $ python3 -m pip install pytak[with_takproto]

Alternative, installing from a Debian package::

    $ TK TK

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