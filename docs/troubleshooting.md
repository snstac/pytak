
# Common Problems

## My CoT Events are NOT showing up in TAK

1. Try setting your `COT_URL` to stdout: `COT_URL=log://stdout` - This will print the CoT events to your console or log. Use this to verify your PyTAK-derived tool is actually spitting out CoT Events.
2. Try settting your `COT_URL` to the IP of your EUD (ATAK, iTAK, WinTAK): `COT_URL=tcp://my-phone-ip-address:4242`.
3. If using Mesh SA, ensure your network supports Multicast. 


## `PEM pass phrase:` Prompt

The `PEM pass phrase:` prompt can be the result of using a private-key encrypted (password-protected) **PYTAK_TLS_CLIENT_KEY** file. This is the default behavior of TAK Server's `makeCert.sh` tool. TAK Server's default password is defined in `CoreConfig.xml`.

Depending on the security requirements in your operating environment, there are three possible procedures to choose from to resolve this prompt: 

1. Set the encryption password with the **PYTAK_TLS_CLIENT_PASSWORD** configuration parameter. For example: **PYTAK_TLS_CLIENT_PASSWORD=abc123**
2. Remove the PEM pass phrase: `openssl rsa -in pytak.key -out pytak.nopass.key`
2. Accept this as the way of life and enter a pass phrase every time you restart this software.


# Windows Problems

Set DEBUG env var in PowerShell:

`$env:DEBUG=1`

Check with:

`$env:DEBUG`
