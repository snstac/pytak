Examples
========

The following Python 3.7+ code example creates a TAK Client that generates ``takPong`` 
CoT every 20 seconds, and sends them to a TAK Server at 
``tcp://takserver.example.com:8087`` (plain / clear TCP).

* For secure TLS, see `TLS Support <https://github.com/snstac/pytak#tls-support>`_ below. 

To run this example as-is, save the following code-block out to a file named 
``example.py`` and run the command ``python3 example.py``::

    #!/usr/bin/env python3

    import asyncio
    import xml.etree.ElementTree as ET

    from configparser import ConfigParser

    import pytak


    class MySerializer(pytak.QueueWorker):
        """
        Defines how you process or generate your Cursor-On-Target Events.
        From there it adds the COT Events to a queue for TX to a COT_URL.
        """

        async def handle_data(self, data):
            """
            Handles pre-COT data and serializes to COT Events, then puts on queue.
            """
            event = data
            await self.put_queue(event)

        async def run(self, number_of_iterations=-1):
            """
            Runs the loop for processing or generating pre-COT data.
            """
            while 1:
                data = tak_pong()
                await self.handle_data(data)
                await asyncio.sleep(20)


    def tak_pong():
        """
        Generates a simple takPong COT Event.
        """
        root = ET.Element("event")
        root.set("version", "2.0")
        root.set("type", "t-x-d-d")
        root.set("uid", "takPong")
        root.set("how", "m-g")
        root.set("time", pytak.cot_time())
        root.set("start", pytak.cot_time())
        root.set("stale", pytak.cot_time(3600))
        return ET.tostring(root)


    async def main():
        """
        The main definition of your program, sets config params and
        adds your serializer to the asyncio task list.
        """
        config = ConfigParser()
        config["mycottool"] = {"COT_URL": "tcp://takserver.example.com:8087"}
        config = config["mycottool"]

        # Initializes worker queues and tasks.
        clitool = pytak.CLITool(config)
        await clitool.setup()

        # Add your serializer to the asyncio task list.
        clitool.add_tasks(set([MySerializer(clitool.tx_queue, config)]))

        # Start all tasks.
        await clitool.run()


    if __name__ == "__main__":
        asyncio.run(main())
