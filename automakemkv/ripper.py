import os

import pyudev

from .mediaInfo import getTitleInfo

KEY = 'DEVNAME'

def main( root="/dev/disk/by-uuid" ):

    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem='block')
    for action, device in monitor:
        if KEY not in device.properties:
            continue

        info = getTitleInfo( device.properties[KEY], root )
        print( info )
