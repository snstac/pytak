## Clients & Servers

PyTAK is used in mission criticial environments, every day, across all official 
[TAK Products](https://tak.gov>):

* [WinTAK](https://tak.gov/)
* [ATAK](https://play.google.com/store/apps/details?id=com.atakmap.app.civ)
* [iTAK](https://apps.apple.com/us/app/itak/id1561656396)
* [TAKX](https://tak.gov/)
* [TAK Server](https://tak.gov/)

PyTAK has been tested and is compatible with many situational awareness (SA) & common 
operating picture (COP) systems:

* [taky](https://github.com/tkuester/taky)
* [Free TAK Server (FTS/FreeTAKServer)](https://github.com/FreeTAKTeam/FreeTakServer)
* RaptorX
* COPERS


## Input, Output & Network Protocols

PyTAK supports the following I/O & network protocols:

* TLS Unicast: ``tls://host:port``
* TCP Unicast: ``tcp://host:port``
* UDP Multicast: ``udp://group:port`` (aka **Mesh SA**)
* UDP Unicast: ``udp://host:port``
* UDP Broadcast: ``udp+broadcast://network:port``
* UDP Write-only: ``udp+wo://host:port``
* stdout or stderr: ``log://stdout`` or ``log://stderr``


## TAK Protocol Payload - Version 1 (Protobuf)

PyTAK natively sends & receives ["TAK Protocol Payload - Version 0"](https://github.com/deptofdefense/AndroidTacticalAssaultKit-CIV/blob/master/commoncommo/core/impl/protobuf/protocol.txt) (plain UTF-8 XML CoT).

To allow PyTAK to send & receive "TAK Protocol Payload - Version 1" Protobuf, install the optional [takproto](https://github.com/snstac/takproto) Python module::

When installing PyTAK::

    python3 -m pip install pytak[with_takproto]

Alternative, installing from a Debian package::

    sudo apt update -y
    wget https://github.com/snstak/takproto/releases/latest/download/takproto_latest_all.deb
    sudo apt install -f ./takproto_latest_all.deb


## Python 3.6+

PyTAK requires Python 3.6 or above and WILL NOT work on Python versions below 3.6. It 
should run on almost any platform that supports Python 3.6+, including Linux, Windows, 
Raspberry Pi, Android, et al.


## FreeTAKServer

FTS (Free TAK Server) has built-in anti-Denial-of-Service (DoS) support, which 
restricts the number of CoT Events a client can send to a listening TCP Port. 
Currently this FTS feature cannot be disabled or changed, so clients must meter 
their input speed.

To use a PyTAK-based client with FTS, set the ``FTS_COMPAT`` configuration parameter 
to ``True``. This will cause the PyTAK client to sleep a random number of seconds 
between transmitting CoT to a FTS server::

    FTS_COMPAT=True

Alternatively you can specify a static sleep period by setting ``PYTAK_SLEEP`` to an 
integer number of seconds::

    PYTAK_SLEEP=3
