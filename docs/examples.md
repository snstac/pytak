## Send TAK Data

The following Python 3.7+ code example creates a TAK Client that generates `takPong`
CoT every 20 seconds, and sends them to a TAK Server at
`tcp://takserver.example.com:8087` (plain / clear TCP).

To run this example as-is, save the following code-block out to a file named
`send.py` and run the command `python3 send.py`::

```python
{!examples/send.py!}
```

## Send & Receive TAK Data

TK TK TK

To run this example as-is, save the following code-block out to a file named
`send_receive.py` and run the command `python3 send_receive.py`::

```python
{!examples/send_receive.py!}
```

## Generate COTs using built-in helper functions

This script shows some basic and advanced use cases on how you can build COTs using the available helper functions from the library.  
To run this example as-is, save the following code-block out to a file named
`cot_builder.py`, change the configuration to match your TAK server, and run the command `python3 cot_builder.py`::

```python
{!examples/cot_builder.py!}
```

## Generate a COT deleter message

This script shows the capability to generate a COT that deletes a previously sent COT by matching the `uid`. To run this example as-is, save the following code-block out to a file named
`cot_deleter.py`, change the configuration to match your TAK server, and run the command `python3 cot_deleter.py`::

```python
{!examples/cot_deleter.py!}
```
