# Compatibility

## Clients & Servers

PyTAK is used in mission critical environments, every day, across all official
[TAK Products](https://tak.gov):

* [WinTAK](https://tak.gov/)
* [ATAK](https://play.google.com/store/apps/details?id=com.atakmap.app.civ)
* [iTAK](https://apps.apple.com/us/app/itak/id1561656396)
* [TAKX](https://tak.gov/)
* [TAK Server](https://tak.gov/)

PyTAK has also been tested with:

* [taky](https://github.com/tkuester/taky)
* [Free TAK Server (FTS/FreeTAKServer)](https://github.com/FreeTAKTeam/FreeTakServer)
* RaptorX
* COPERS

---

## Network Protocols

| URL scheme | Transport |
|---|---|
| `tcp://host:port` | TCP unicast (plain text) |
| `tls://host:port` | TLS unicast (encrypted, mTLS) |
| `udp://group:port` | UDP multicast (Mesh SA) |
| `udp://host:port` | UDP unicast |
| `udp+broadcast://network:port` | UDP broadcast |
| `udp+wo://host:port` | UDP write-only (no port bind) |
| `log://stdout` / `log://stderr` | Console output (debug) |
| `marti://host:port` | TAK Server Marti REST API (TLS) |
| `marti+http://host:port` | TAK Server Marti REST API (HTTP) |
| `tak://...` | TAK enrollment deep-link |

---

## TAK Protocol Payload

PyTAK natively sends and receives [TAK Protocol Payload - Version 0](https://github.com/deptofdefense/AndroidTacticalAssaultKit-CIV/blob/master/commoncommo/core/impl/protobuf/protocol.txt) (plain UTF-8 XML CoT). This is the default and works with all TAK clients.

To enable TAK Protocol Payload - Version 1 (Protobuf), install the optional [takproto](https://github.com/snstac/takproto) module and set `TAK_PROTO=1`:

=== "pip"
    ```sh
    pip install pytak[with_takproto]
    ```

=== "Debian package"
    ```sh
    wget https://github.com/snstac/takproto/releases/latest/download/takproto_latest_all.deb
    sudo apt install -f ./takproto_latest_all.deb
    ```

!!! warning "Protobuf and iTAK"
    TAK Protocol v1 (Protobuf) may not work reliably with all versions of iTAK. Use `TAK_PROTO=0` (XML) unless you have confirmed Protobuf support on all clients.

---

## Python Version

PyTAK requires Python **3.7 or later**. It runs on Linux, Windows, macOS, Raspberry Pi, and Android (via Termux or similar).

---

## FreeTAKServer

Free TAK Server (FTS) has built-in anti-DoS rate limiting that restricts how fast clients can send CoT events. This cannot be disabled on the server side.

To work with FTS, enable compatibility mode:

```ini
FTS_COMPAT = 1
```

Or use a fixed sleep between events:

```ini
PYTAK_SLEEP = 3
```

See [Configuration: FTS_COMPAT](configuration.md#fts_compat) for details.
