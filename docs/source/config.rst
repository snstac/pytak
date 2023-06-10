Configuration
=============

PyTAK's configuration parameters can be set two ways:

1. In an INI-style configuration file, typically ``config.ini``
2. As environment variables.

PyTAK has the following built-in configuration parameters:

.. describe:: COT_URL (optional)

  Destination for Cursor on Target messages. Defaults to ``udp://239.2.3.1:6969`` (ATAK Multicast UDP / Mesh SA Default)

TAK_PROTO
  Sets TAK Protocol to use for CoT output, one of: 0 (XML), 2 (Mesh), 2 (Stream).

  * Default: 0 (XML)

DEBUG
  Sets debug-level logging.

  * Default: False

FTS_COMPAT
  If set, implements random-seconds-sleep period to avoid FTS DoS protections.

  * Default: False

PYTAK_SLEEP
  If set, implements given sleep period of seconds between emitting CoT Events.

  * Default: 0

PREF_PACKAGE
  (If PyTAK is installed with optional with_crypto support.)

  PyTAK supports importing TAK Data Packages containing TAK Server connection settings, 
  TLS certificates, etc. 

  To use a .zip file with PyTAK, set the ``PREF_PACKAGE`` config parameter to the 
  path to the .zip file.

  For example, given a Pref Package named ``ADSB3_FIRE.zip``, you could either:

  Using ``config.ini``: Add the line ``PREF_PACKAGE=ADSB3_FIRE.zip``

  Using the commandline of a utility: Add the argument ``-p DSB3_FIRE.zip``


TLS Support
-----------

PyTAK can send & receive data over TLS by setting the following configuration 
parameters (at a minimum)::

1) Specify ``tls://`` in the CoT Destination URL, for example: ``tls://takserver.example.com:8089``
2) Specify the TLS Cert in ``PYTAK_TLS_CLIENT_CERT``.

Client Certificates, Client Key, CA Certificate & Key must be specified in PEM format.

*N.B*: Encrypted private keys are not supported and must be saved in clear-text: ``openssl rsa -in my_cert.key.pem -out my_cert-nopass.key.pem``

PYTAK_TLS_CLIENT_CERT
  Path to a file containing the Client Certificate for PyTAK. File must be 
  unencrypted plain-text PEM.
  
  This file can contain both the Client Cert & Client Key, or the Client Cert alone. In 
  the later case (cert alone), ``PYTAK_TLS_CLIENT_KEY`` must be set to the Client Key.

  For example, to connect to a TAK Server listening for TLS on port 8089::

      PYTAK_TLS_CLIENT_CERT=client_cert_and_key.pem
      COT_URL=tls://tak.example.com:8089

**Optional TLS Configuration**

PYTAK_TLS_CLIENT_KEY
  Path to a file containing the Client Private Key for the associated 
  ``PYTAK_TLS_CLIENT_CERT``. File must be unencrypted plain-text PEM.

PYTAK_TLS_DONT_VERIFY
  Disable destination TLS Certificate Verification. Will print a WARNING if set.

PYTAK_TLS_DONT_CHECK_HOSTNAME
  Disable destination TLS Certificate Common Name (CN) Verification. Will print a 
  WARNING if set.

PYTAK_TLS_CLIENT_CAFILE
  Path to a file containing the CA Trust Store to use for remote certificate verification.

PYTAK_TLS_CLIENT_CIPHERS
  Colon (":") seperated list of TLS Cipher Suites to allow. 

  For example: ``PYTAK_TLS_CLIENT_CIPHERS=ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384``

  * Default: ``ALL`` 
