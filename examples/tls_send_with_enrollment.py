#!/usr/bin/env python3

import asyncio

from configparser import ConfigParser

import pytak


class MySerializer(pytak.QueueWorker):
    """
    Defines how you process or generate your Cursor on Target Events.
    From there it adds the CoT Events to a queue for TX to a COT_URL.
    """

    async def handle_data(self, data):
        """Handle pre-CoT data, serialize to CoT Event, then puts on queue."""
        event = data
        await self.put_queue(event)

    async def run(self, number_of_iterations=-1):
        """Run the loop for processing or generating pre-CoT data."""
        while 1:
            data = pytak.gen_cot(lat=37.76, lon=-122.4975)
            await self.handle_data(data)
            await asyncio.sleep(20)


async def main():
    """Main definition of your program, sets config params and
    adds your serializer to the asyncio task list.
    """
    config = ConfigParser()
    # Generate certs with:
    # $ sudo /opt/tak/certs/makeCert.sh client pytak-test01
    config["tls_send"] = {
        "COT_URL": "tls://takserver.example.com:8089",
        "PYTAK_TLS_CERT_ENROLLMENT_USERNAME": "xxx",
        "PYTAK_TLS_CERT_ENROLLMENT_PASSWORD": "yyy",
        "PYTAK_TLS_DONT_VERIFY": True,
        "PYTAK_TLS_DONT_CHECK_HOSTNAME": True,
        # "DEBUG": True,
        "TAK_PROTO": 0,
    }
    config = config["tls_send"]

    # Initializes worker queues and tasks.
    clitool = pytak.CLITool(config)
    await clitool.setup()

    # Add your serializer to the asyncio task list.
    clitool.add_tasks(set([MySerializer(clitool.tx_queue, config)]))

    # Start all tasks.
    await clitool.run()


if __name__ == "__main__":
    asyncio.run(main())
