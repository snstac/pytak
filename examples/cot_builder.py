#!/home/henri.berisha/anaconda3/envs/tak/bin/python3

import asyncio
import os
import sys
import xml.etree.ElementTree as ET
from configparser import ConfigParser
from typing import Optional, Tuple, Union

import pytak


# for TAK, time should have this format: "%Y-%m-%dT%H:%M:%S.%fZ"
# does not matter if it has milliseconds, or no, also the digits for the milliseconds dont matter

# If you are looking to push simple minimal CoT events, this is the way to go
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
    # this is a wrapper function for: gen_cot_xml(...)
    return pytak.gen_cot(lat=lat, lon=lon, ce=ce, hae=hae, le=le, uid=uid, stale=stale, cot_type=cot_type)  # <class 'bytes'>


# This is the advanced way to send a more wholesome CoT with support for all attributes for the `event` element
def generate_detailed_cot_event():
    lat = "40.77538253016966"
    lon = "-73.97084063459074"
    hae = "10"
    ce = pytak.DEFAULT_COT_VAL
    le = pytak.DEFAULT_COT_VAL
    uid = "Detailed CoT"
    stale = 60
    cot_type = None
    cot_how = "h-i-h"
    timestamp = None
    access = pytak.MIL_STD_6090_ACCESS_VALUES.NATO_SECRET
    caveat = "CUI"
    releasableto = "GBR"
    qos = "9-r-g"
    opex = "o-Easy CoTs"
    callsign = "MyDetailedCoT"
    remarks = "TestRemark"
    flow_tags_include = True
    flow_tags_custom = None

    # Might be better to call all args by name rather than position, this way may skip what are not needed.
    # If calling by position, you need to provide them all
    base_cot_event: Union[ET.Element, bytes, None] = pytak.gen_cot_detailed_xml(
        lat, lon, hae, ce, le, uid, stale, cot_type, cot_how, timestamp, access, caveat, releasableto, qos, opex, callsign, remarks, flow_tags_include, flow_tags_custom
    )

    if isinstance(base_cot_event, ET.Element):
        cot = b"\n".join([pytak.DEFAULT_XML_DECLARATION, ET.tostring(base_cot_event)])
    
    return cot  # <class 'bytes'>


# This is based on the minimal CoT event, but showcasing how to add more attributes and subelements for the `detail` element
def generate_minimum_cot_event_with_detail():
    lat = "40.77538253016966"
    lon = "-73.97084063459074"
    ce = pytak.DEFAULT_COT_VAL
    hae = "10"
    le = pytak.DEFAULT_COT_VAL
    uid = "MinimalCoT"
    stale = 60
    cot_type = None

    # Might be better to call all args by name rather than position, this way may skip what are not needed.
    # If calling by position you need to provide them all
    base_cot_event: Union[ET.Element, bytes, None] = pytak.gen_cot_xml(lat, lon, ce, hae, le, uid, stale, cot_type)

    # here modify the base event with whatever you need
    tree = ET.ElementTree(base_cot_event)
    event: ET.Element = tree.getroot()
    detail: ET.Element = event.find("detail")

    remark = ET.Element("remarks")
    text: str = f"I added remarks to the minimal CoT event"
    remark.text = text
    detail.append(remark)

    # similar you can append more subelements to the `detail element

    # in the end dont append detail to event, it is already appended, you are just adding subelements to detail
    if isinstance(base_cot_event, ET.Element):
        cot = b"\n".join([pytak.DEFAULT_XML_DECLARATION, ET.tostring(event)])
    
    return cot  # <class 'bytes'>


# This is based on the advanced COT event, but showcasing how to add more attributes and subelements for the `detail` element
def generate_detailed_cot_event_with_more_details():
    lat = "40.77538253016966"
    lon = '-73.97084063459074'
    hae = "10"
    ce = pytak.DEFAULT_COT_VAL
    le = pytak.DEFAULT_COT_VAL
    uid = "Detail Edited"
    stale = 60
    cot_type = None
    cot_how = "h-i-h"
    timestamp = None
    access = pytak.MIL_STD_6090_ACCESS_VALUES.NATO_SECRET
    caveat = "CUI"
    releasableto = "GBR"
    qos = "9-r-g"
    opex = "o-Easy CoTs"
    callsign = "DetailedCoTwithTrack"
    remarks = "TestRemark"
    flow_tags_include = True
    flow_tags_custom = None

    # here callsign left out on purpose, so it can be edited later
    # here arguments are given by name, hence we do not have to provide all of them, order does not matter either. 
    # What is not provided will default to its preset value
    base_cot_event: Union[ET.Element, bytes, None] = pytak.gen_cot_detailed_xml(
        lat=lat, lon=lon, flow_tags_include=False, uid=uid
    )

    # here modify the base event with whatever you need
    tree = ET.ElementTree(base_cot_event)
    event: ET.Element = tree.getroot()
    detail: ET.Element = event.find("detail")

    # similarly, can add other subelements depending on the use case
    # subelement `contact` with `callsign` as its attribute. This is being appended directly to `detail`
    ET.SubElement(detail, "contact", {"callsign": callsign})

    dummy_heading = 270  # deg
    dummy_speed = 7.8  # m/s
    track = ET.Element("track")

    #  Append heading only if available
    if 0.0 <= dummy_heading <= 359.99:
        track.set("course", str(dummy_heading))
    track.set("speed", str(dummy_speed))  # # COT Speed is meters/second
    detail.append(track)

    if isinstance(base_cot_event, ET.Element):
        cot = b"\n".join([pytak.DEFAULT_XML_DECLARATION, ET.tostring(base_cot_event)])
    
    return cot  # <class 'bytes'>


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
        print(event, type(event))
        await self.put_queue(event)

    async def run(self, number_of_iterations=-1):
        """
        Runs the loop for processing or generating pre-COT data.
        """
        while 1:
            # data = generate_minimum_cot_event()
            # data = generate_detailed_cot_event()
            # data = generate_minimum_cot_event_with_detail()
            data = generate_detailed_cot_event_with_more_details()
            await self.handle_data(data)
            await asyncio.sleep(5)  # sleep for 30 secs


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
