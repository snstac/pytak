PyTAK's configuration parameters can be set two ways:

1. In an INI-style configuration file, typically ``config.ini``
2. As environment variables.

PyTAK has the following built-in configuration parameters:

* **`COT_URL`**
    * Default: ``udp+wo://239.2.3.1:6969`` (TAK Mesh SA, Multicast UDP, write-only)

    Destination for TAK Data (Cursor on Target Events). Supported values are:
    
    * TLS Unicast: ``tls://host:port``
    * TCP Unicast: ``tcp://host:port``
    * UDP Multicast: ``udp://group:port`` (aka **Mesh SA**)
    * UDP Unicast: ``udp://host:port``
    * UDP Broadcast: ``udp+broadcast://network:port``
    * UDP Write-only: ``udp+wo://host:port``
    * stdout or stderr: ``log://stdout`` or ``log://stderr``

    **N.B.** `+wo` modifier stands for 'write-only', and allows multiple PyTAK 
    applications to run on a single bound-interface without monopolizing a port. If you're getting a 'cannot bind to port' or 'port occupied error', try adding the `+wo` modifier.


* **`TAK_PROTO`**
    * Default: `0` ("TAK Protocol - Version 0", XML)

    Sets TAK Protocol to use for CoT output, one of:

    * `0` ("TAK Protocol - Version 0", XML)
    * `2` ("TAK Protocol - Version 1" Mesh, Protobuf)
    * `3` ("TAK Protocol - Version 1" Stream, Protobuf) TK (FIXME: Is this correct?)


* **`DEBUG`**
    * Default: `0` (False)

    Sets debug-level logging. Any value other than `0` is considered True. False if unset.


* **`FTS_COMPAT`** 
    * Default: `0` (disabled)
    
    If set, implements random-seconds-sleep period to avoid FTS DoS protections.


* **`PYTAK_SLEEP`**
    * Default: `0` (disabled)

    If set, implements given sleep period of seconds between emitting CoT Events. Only supports integers (seconds), not sub-seconds.


* **`PREF_PACKAGE`**
    
    **N.B.** PyTAK must be installed with *with_crypto* support, or the Python `cryptography` module must be installed.

    PyTAK supports importing TAK Data Packages containing TAK Server connection settings, TLS certificates, etc. 

    To use a .zip file with PyTAK, set the ``PREF_PACKAGE`` config parameter to the path to the .zip file.

    For example, given a Pref Package named ``ADSB3_FIRE.zip``, you could either:

    * Using ``config.ini``: Add the line ``PREF_PACKAGE=ADSB3_FIRE.zip``
    * Using the commandline of a utility: Add the argument ``-p ADSB3_FIRE.zip``


* **`PYTAK_MULTICAST_LOCAL_ADDR`**
    * Default: `0.0.0.0`

    For systems with multiple IP network interfaces, specifies which IP interface to use for the multicast group.

* **`PYTAK_MULTICAST_TTL`**
    * Default: `1`

    For clients that are more than one hop away from the TAK broadcast network, specifies the time-to-live (TTL) of multicast packets. This is helpful when the client is hosted in a virtual machine or container with an overlay network.

* **`PYTAK_NO_HELLO`**
    * Default: `False`

    Disable the "Hello" Event transmitted by PyTAK on initial connection to a TCP or UDP host.


## CoT Event Attributes

* **`COT_STALE`**
    * Default: `120` (2 minutes)

    CoT Event stale time in seconds.


## TLS Support

PyTAK supports sending & receiving TAK Data over TLS. This section describes the various configuration parameters that can be set for TLS network connections.

**Minimum TLS Configuration**

At a minimum, to use TLS with PyTAK, the following two conditions must be met:

1. Specify ``tls://`` in the ``COT_URL`` config parameter.
    
    For example: ``COT_URL=tls://takserver.example.com:8089``

2. Specify the path to the TLS cert with the ``PYTAK_TLS_CLIENT_CERT`` config parameter.

    For example: ``PYTAK_TLS_CLIENT_CERT=/etc/pytak-cert.pem``

**Please Note**

* Client Certificates, Client Key, CA Certificate & Key must be specified in PEM format.

### TLS Verifications

PyTAK uses standard TLS Verifications when establishing TLS sockets to TAK Servers.

1. TLS Server Common Name Verification

2. TLS Server Certificate Verification

### TLS Configuration Parameters

PyTAK can send & receive data over TLS by setting the following configuration parameters:

* **`PYTAK_TLS_CLIENT_CERT`**

    Path to a file containing the unencrypted plain-text PEM format Client Certificate.
    
    This file can contain both the Client Cert & Client Key, or the Client Cert alone. In the later case (cert alone), ``PYTAK_TLS_CLIENT_KEY`` must be set to the Client Key.

    For example, to connect to a TAK Server using TLS on port 8089:

        PYTAK_TLS_CLIENT_CERT=/etc/pytak_client_cert_and_key.pem
        COT_URL=tls://takserver.example.com:8089

    For reference, the TAK Server `CoreConfig.xml` would contain a line like this:

        <input auth="x509" _name="tlsx509" protocol="tls" port="8089" archive="false"/>

* **`PYTAK_TLS_CLIENT_KEY`** (optional)

    Path to a file containing the unencrypted plain-text PEM format Client Private Key for the associated 
    ``PYTAK_TLS_CLIENT_CERT``. 


* **`PYTAK_TLS_DONT_VERIFY`**
    * Default: `0` (verify)

    When set to `1` (don't verify), Disable destination TLS Certificate Verification. Will print a WARNING if set to `1`.


* **`PYTAK_TLS_DONT_CHECK_HOSTNAME`**
    * Default: `0` (verify)

    When set to `1` (don't verify), disables destination TLS Certificate Common Name (CN) Verification. Will print a WARNING if set to `1`.


* **`PYTAK_TLS_CLIENT_CAFILE`** (optional)

    Path to a file containing the CA Trust Store to use for remote certificate verification.


* **`PYTAK_TLS_SERVER_EXPECTED_HOSTNAME`** (optional)

  Expected hostname or CN of the connected server. Not used unless verifying hostname.


* **`PYTAK_TLS_CLIENT_CIPHERS`** (optional)
    * Default: ``ALL`` 

    Colon ("`:`") seperated list of TLS Cipher Suites to allow. 

    For example, to set FIPS-only ciphers:
    
    ``PYTAK_TLS_CLIENT_CIPHERS=ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384``


* **`PYTAK_TLS_CLIENT_PASSWORD`** (optional)

    Password for PKCS#12 (.p12) password protected certificates or password protected Private Keys.
