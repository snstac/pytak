## Debian, Ubuntu, Raspberry Pi

PyTAK is distributed as a Debian package (``.deb``). PyTAK should be compatible with most contemporary system-Python versions from Python 3.6 onward. 

To install PyTAK, download the pytak package and install using apt:

```sh
sudo apt update -y
wget https://github.com/snstac/pytak/releases/latest/download/python3-pytak_latest_all.deb
sudo apt install -f ./python3-pytak_latest_all.deb
```

### Data Package Support

To install PyTAK with Deta Package support, you must also install the [cryptography](https://cryptography.io/en/latest/installation/) Python module using apt:

```sh
sudo apt update -y
sudo apt install -y python3-cryptography
```

### TAK Protocol - Version 1 Support

To install PyTAK with "TAK Protocol - Version 1" Protobuf support, you must also install the [takproto](https://github.com/snstac/takproto) Python module.

To install takproto, download the deb package and install using apt::

```sh
sudo apt update -y
wget https://github.com/snstak/takproto/releases/latest/download/python3-takproto_latest_all.deb
sudo apt install -f ./python3-takproto_latest_all.deb
```

## Install from Python Package Index (PyPI)

You can install from [Python Package Index (PyPI)](https://pypi.org/) or from source. Both of these methods will require manual installation of additional libraries.

### Prerequisites

#### Debian, Ubuntu & Raspberry Pi OS

Install [LibFFI](https://sourceware.org/libffi/):
```sh
sudo apt update -y
sudo apt install libffi-dev
```

#### CentOS & RedHat

Install LibFFI:

```sh
sudo yum install libffi-devel
```

### Install PyTAK

```sh
python3 -m pip install pytak
python3 -m pip install pytak[with_crypto]
python3 -m pip install pytak[with_takproto]
```

## Install from Source

```sh
git clone https://github.com/snstac/pytak.git
cd pytak/
python3 -m pip install .
```
