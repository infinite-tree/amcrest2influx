import asyncio
import datetime
import re
import time

from aioinflux import InfluxDBClient
from amcrest import AmcrestCamera

# Amcrest event examples:
# Code: VideoLoss
# Payload: {'Code': 'VideoLoss', 'action': 'Start', 'index': '5'}
# Code: VideoLoss
# Payload: {'Code': 'VideoLoss', 'action': 'Stop', 'index': '5'}
#
# Code: NTPAdjustTime
# Payload: {'Code': 'NTPAdjustTime', 'action': 'Pulse', 'index': '0'}
#
# Code: RecordDelete
# Payload: {'Code': 'RecordDelete', 'action': 'Pulse', 'index': '0'}


def loadConfig():
    import config
    return dict(config.config)


class InfluxWrapper(object):
    def __init__(self, config):
        self.Config = config['influx']
        self.Location = self.Config['location']
        self.Influx = InfluxDBClient(self.Config['host'],
                                     self.Config['port'],
                                     username=self.Config['username'],
                                     password=self.Config['password'],
                                     database=self.Config['database'],
                                     ssl=self.Config['ssl'])

    def getTime(self):
        now = datetime.datetime.utcnow()
        return now.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    async def sendMeasurement(self, measurement_name, index, value):
        point = {
            "measurement": measurement_name,
            "tags": {
                "location": self.Location,
                "index": index
            },
            "time": self.getTime(),
            "fields": {
                "value": float(value)
            }
        }
        print("Sending %s-> %s: %s"%(measurement_name, index, value))
        await self.Influx.write(point)


class AmcrestMonitor(object):
    def __init__(self, config):
        self.Config = config["amcrest"]
        self.NVR = AmcrestCamera(self.Config["host"],
                                 self.Config["port"],
                                 self.Config["username"],
                                 self.Config["password"]).camera
        self.InfluxClient = InfluxWrapper(config)

        # Init Camera Loss Monitoring
        self.EventStates = {}
        for event in self.Config["events"]:
            if event == "VideoLoss":
                self._getCamerasWithAlarms()
        
        # TODO: Init other events

    def _getCamerasWithAlarms(self):
        for line in self.NVR.video_loss_detect_config.split("\r\n"):
            m = re.match("table\.LossDetect\[(\d+)\].Enable=true", line)
            if m and m.groups():
                camera = m.groups()[0]
                # Invert status for Influx to match common conventions
                self.EventStates.setdefault("VideoLoss", {})[camera] = True
    
    @asyncio.coroutine
    async def reportStatus(self):
        while True:
            tasks = []
            for event_type, data in self.EventStates.items():
                for k, v in data.items():
                    tasks.append(self.InfluxClient.sendMeasurement(event_type, k, v))
            
            await asyncio.gather(*tasks)
            await asyncio.sleep(60)

    @asyncio.coroutine
    async def monitorEvents(self):
        async for code, payload in self.NVR.async_event_actions("All", timeout_cmd=(30.0, 3600)):
            print("Event received: %s"%payload)
            if code in self.EventStates:
                idx = payload['index']
                if idx in self.EventStates[code]:
                    if code == "VideoLoss":
                        # Invert status for Influx to match common conventions
                        if payload['action'] == "Start":
                            self.EventStates[code][idx] = False
                        else:
                            self.EventStates[code][idx] = True

async def main():
    config = loadConfig()
    monitor = AmcrestMonitor(config)
    await asyncio.gather(monitor.reportStatus(), monitor.monitorEvents())

asyncio.run(main())
