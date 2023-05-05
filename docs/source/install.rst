
Installation
============

Debian, Ubuntu, Raspberry Pi
----------------------------

PyTAK is distributed as a Debian package (``.deb``). PyTAK should be compatible with 
most contemporary system-Python versions from Python 3.6 onward. The `Advanced Package 
Tool (apt) <https://wiki.debian.org/PackageManagement>`_ is used to install this 
and other related packages.

To install PyTAK, download the pytak package and install using apt::

    $ sudo apt update -y
    $ wget https://github.com/snstac/pytak/releases/latest/download/python3-pytak_latest_all.deb
    $ sudo apt install -f ./python3-pytak_latest_all.deb

Data Package Support
####################

To install PyTAK with Deta Package support, you must also install the Python 
`cryptography <https://cryptography.io/en/latest/installation/>`_ module using apt::

    $ sudo apt update -y
    $ sudo apt install -y python3-cryptography

TAK Protocol Version 1 (protobuf) Support
#########################################

To install PyTAK with TAK Protocol Version 1 (protobuf) support, you must also install 
the Python TAKProto module `takproto <https://github.com/snstac/takproto>`_.

To install the TAKProto module, download the takproto package and install using apt::

    $ sudo apt update -y
    $ wget https://github.com/snstak/takproto/releases/latest/download/python3-takproto_latest_all.deb
    $ sudo apt install -f ./python3-takproto_latest_all.deb


Alternative Installation
------------------------

You can install from PyPI or from source. Both of these methods will require manual 
installation of additional libraries.

1a. Debian, Ubuntu, Raspberry Pi: Install `LibFFI <https://sourceware.org/libffi/>`_::

    $ sudo apt update -y
    $ sudo apt install libffi-dev

1b. RedHat, CentOS: Install `LibFFI <https://sourceware.org/libffi/>`_::

    $ sudo yum install libffi-devel

2a. Install PyTAK from the Python Package Index::

    $ python3 -m pip install pytak
    $ python3 -m pip install pytak[with_crypto]
    $ python3 -m pip install pytak[with_takproto]

2b. Install PyTAK from source::

    $ git clone https://github.com/snstac/pytak.git
    $ cd pytak/
    $ python3 -m pip install .
