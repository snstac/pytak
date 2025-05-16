import asyncio
import os
import sys
import xml.etree.ElementTree as ET
from configparser import ConfigParser
from typing import Optional, Tuple, Union

import pytak

""" 
The purpose of this example is to show how to send a CoT message that deletes a previous CoT
Just provide the uid of the COT to be deleted
Now you do not have to wait until the stale time has passed for the marker to be removed
"""

def generate_minimum_cot_event():
    lat = "40.77538253016966"  # do not do bytes, preferred is float, or str
    lon = "-73.97084063459074"  # do not do bytes, preferred is float, or str
    hae = "10"
    ce = pytak.DEFAULT_COT_VAL
    le = pytak.DEFAULT_COT_VAL
    uid = "Minimal CoT"
    stale = 60  # 60 seconds until it stalls
    cot_type = None  # This will cause it to default to "a-u-G". Choose your CoT type for the desired marker

    # leveraging pytak's `gen_cot` function
    return pytak.gen_cot(lat=lat, lon=lon, ce=ce, hae=hae, le=le, uid=uid, stale=stale, cot_type=cot_type)  # <class 'bytes'>


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
        print(event, type(event), end="\n\n")
        await self.put_queue(event)

    async def run(self, number_of_iterations=-1):
        """
        Runs the loop for processing or generating pre-COT data.
        """
        while 1:
            data = generate_minimum_cot_event()
            await self.handle_data(data)
            await asyncio.sleep(5)
            data = pytak.gen_delete_cot_xml("Minimal CoT") # just provide the uid of cot to delete
            await self.handle_data(data)
            await asyncio.sleep(5)


async def main():
    """
    The main definition of your program, sets config params and
    adds your serializer to the asyncio task list.
    """
    # your TAK server config here
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