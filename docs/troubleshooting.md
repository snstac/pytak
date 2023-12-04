
# Common Problems

## My CoT Events are NOT showing up in TAK

1. Try setting your `COT_URL` to stdout: `COT_URL=log://stdout` - This will print the CoT events to your console or log. Use this to verify your PyTAK-derived tool is actually spitting out CoT Events.
2. Try settting your `COT_URL` to the IP of your EUD (ATAK, iTAK, WinTAK): `COT_URL=tcp://my-phone-ip-address:4242`.
3. If using Mesh SA, ensure your network supports Multicast. 


## `Enter PEM pass phrase:` Prompt

The `Enter PEM pass phrase:` prompt can be the result of using a private-key encrypted (password-protected) [**PYTAK_TLS_CLIENT_KEY**](https://pytak.readthedocs.io/en/latest/configuration/#tls-configuration-parameters) file. This is the default behavior of TAK Server's `makeCert.sh` tool. TAK Server's default password is defined in `CoreConfig.xml`.

Depending on the security requirements in your operating environment, there are three possible procedures to choose from to resolve this prompt: 

1. Set the encryption password with the [**PYTAK_TLS_CLIENT_PASSWORD**](https://pytak.readthedocs.io/en/latest/configuration/#tls-configuration-parameters) configuration parameter. For example: **PYTAK_TLS_CLIENT_PASSWORD=abc123**
2. Remove the PEM pass phrase: `openssl rsa -in pytak.key -out pytak.nopass.key`
2. Accept this as the way of life and enter a pass phrase every time you restart this software.


# `certificate verify failed:` Error

`ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self signed certificate in certificate chain (_ssl.c:1131)`

The `certificate verify failed` error indicates that the TAK Server is using a certificate that PyTAK does not trust, because it cannot be verified. This is expected behavior for TAK Servers built from the *TAK Server Setup Guide*. 

Many organizations have established their own custom Certificate Authorities (CA). With this comes the need to propagate & establish the CA's authority throughout the organization, including on end-user devices (EUD) like smartphones, tablets and computers. If and EUD holds a copy of the CA's trusted certificate, it can verify (and thus, trust) certificates signed by the CA. If an EUD lacks the CA's authoritative trust (for example, the CA's trust chain PEM is not installed on the EUD), it cannot verify or trust certificates signed by that CA. 

Depending on the security requirements in your operating environment, there are two possible procedures to follow to resolve this error:

1. Set the [**PYTAK_TLS_CLIENT_CAFILE**](https://pytak.readthedocs.io/en/latest/configuration/#tls-configuration-parameters) configuration parameter to a PEM encoded file containing the custom CA trust chain? root? store? TK
2. Bypass remote host TLS certificate verification by setting [**PYTAK_TLS_DONT_VERIFY**](https://pytak.readthedocs.io/en/latest/configuration/#tls-configuration-parameters) to True.


# Windows Problems

Set DEBUG env var in PowerShell:

`$env:DEBUG=1`

Check with:

`$env:DEBUG`
