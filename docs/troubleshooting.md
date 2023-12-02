
# Common Problems

## My CoT Events are showing up in iTAK, WinTAK, ATAK

1. Try setting your `COT_URL` to stdout: `COT_URL=log://stdout` - This will print the CoT events to your console or log. Use this to verify your PyTAK-derived tool is actually spitting out CoT Events.
2. Try settting your `COT_URL` to the IP of your EUD (ATAK, iTAK, WinTAK): `COT_URL=tcp://my-phone-ip-address:4242`.
3. If using Mesh SA, ensure your network supports Multicast. 

# Windows

Set DEBUG env var in PowerShell:

`$env:DEBUG=1`

Check with:

`$env:DEBUG`
