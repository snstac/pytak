# Installation

## Debian, Ubuntu, Raspberry Pi

PyTAK is distributed as a Debian package (`.deb`) and is compatible with Python 3.7 and later.

```sh
sudo apt update -qq
wget https://github.com/snstac/pytak/releases/latest/download/pytak_latest_all.deb
sudo apt install -f ./pytak_latest_all.deb
```

### Optional: TAK Data Package support

Required for importing `.zip` pref packages (TLS certs, server settings):

```sh
sudo apt install -y python3-cryptography
```

### Optional: TAK Protocol v1 (Protobuf) support

Required for Protobuf-encoded CoT (`TAK_PROTO=1`):

```sh
wget https://github.com/snstac/takproto/releases/latest/download/takproto_latest_all.deb
sudo apt install -f ./takproto_latest_all.deb
```

### Optional: Marti REST API / certificate enrollment support

Required for `marti://` transport and automatic `tak://` certificate enrollment:

```sh
sudo apt install -y python3-aiohttp
```

---

## Python Package (pip)

Install from [PyPI](https://pypi.org/project/pytak/) with `pip`. This works on any platform with Python 3.7+.

```sh
python3 -m pip install pytak
```

### Optional extras

Install one or more optional extras to unlock additional features:

| Extra | Feature | Command |
|---|---|---|
| `with_crypto` | TAK Data Packages (`.zip` pref import) | `pip install pytak[with_crypto]` |
| `with_takproto` | TAK Protocol v1 Protobuf | `pip install pytak[with_takproto]` |
| `with_aiohttp` | Marti REST API & cert enrollment | `pip install pytak[with_aiohttp]` |

Install everything at once:

```sh
python3 -m pip install pytak[with_crypto,with_takproto,with_aiohttp]
```

### System prerequisites

Some systems need `libffi` installed before pip can build certain dependencies:

=== "Debian / Ubuntu / Raspberry Pi"
    ```sh
    sudo apt update -qq
    sudo apt install -y libffi-dev
    ```

=== "CentOS / RHEL"
    ```sh
    sudo yum install libffi-devel
    ```

---

## Install from source

```sh
git clone https://github.com/snstac/pytak.git
cd pytak/
python3 -m pip install -e .
```

---

## Windows

PyTAK works on Windows with standard Python 3.7+ from [python.org](https://www.python.org/downloads/).

```powershell
python -m pip install pytak
```

!!! note "UDP multicast on Windows"
    Windows restricts multicast socket binding. If `udp://` (Mesh SA) does not work, use `udp+wo://` (write-only) instead, or connect directly to a TAK Server via `tcp://` or `tls://`.

!!! tip "Setting environment variables in PowerShell"
    ```powershell
    $env:COT_URL = "tcp://takserver.example.com:8087"
    $env:DEBUG = "1"
    ```

---

## Verify installation

```sh
python3 -c "import pytak; print(pytak.__version__)"
```
