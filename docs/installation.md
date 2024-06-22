## Debian, Ubuntu, Raspberry Pi

PyTAK is distributed as a Debian package (``.deb``). PyTAK should be compatible with most contemporary system-Python versions from Python 3.6 onward. 

To install PyTAK, download the pytak package and install using apt:

```sh
sudo apt update -qq
wget https://github.com/snstac/pytak/releases/latest/download/pytak_latest_all.deb
sudo apt install -f ./pytak_latest_all.deb
```

### Optional TAK Data Package Support

To use Data Packages with PyTAK, install the optional [cryptography](https://cryptography.io/en/latest/installation/) Python package:

```sh
sudo apt update -qq
sudo apt install -y python3-cryptography
```

### Optional TAK Protocol - Version 1 Protobuf Support

To use "TAK Protocol - Version 1" Protobuf support, install the optional [takproto](https://github.com/snstac/takproto) Python package.

```sh
sudo apt update -qq
wget https://github.com/snstak/takproto/releases/latest/download/takproto_latest_all.deb
sudo apt install -f ./takproto_latest_all.deb
```

## Python Package

You can install from [Python Package Index (PyPI)](https://pypi.org/) or from source. Both of these methods will require manual installation of additional libraries.

### Prerequisites

#### Debian, Ubuntu & Raspberry Pi OS

Install [LibFFI](https://sourceware.org/libffi/):
```sh
sudo apt update -qq
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
