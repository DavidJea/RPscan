#!/usr/bin/python

# two threads : main one launches mobilesim continuously
# the other scans for one minute and saves ble samples
# mobilesim thread uses results from last minute and
# starts blescan thread
#
# the two threads work like this
# Time =========================================================>
#             (use 1m)     (use 2m)     (use 3m)     (use 4m)     (use 5m)
# [rpscan1m]->[mobilesim]->[mobilesim]->[mobilesim]->[mobilesim]->[mobilesim]...
#                          ↓            ↓            ↓             ↓
#             [rpscan2m]   [rpscan3m]   [rpscan4m]   [rpscan5m]   [rpscan6m]...

import threading
import time
import subprocess
import blescan
import sys
import bluetooth._bluetooth as bluez

e = threading.Event()

pktTemplate = {"hashkey":"","Protocol":"TCP","Beacon":[],"Accelerometer":[],"topic":"mobile-client-staging","isDeviceMoving":false,"SDK":"2.7.0","Device":{"Model":"Android","UniqueID":""},"V":1,"Date":""}

ORGID = "6748cfa6-4e12-11e6-9188-0242ac110007"

# rpscan class scans for 1 minute, and write results into a file 
class rpscan(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        # init bluetooth
        dev_id = 0
        try:
            sock = bluez.hci_open_dev(dev_id)
        except:
            print "error accessing bluetooth device..."
            sys.exit(1)
        return
        
    def run(self):
        pkts = self.scan_a_minute()     # first launch, scan for a minute data
        self.write_samples_to_file(pkts)
        e.set()                         # tell mobilesim that data is ready, only for the first time
        while True:
            pkts = self.scan_a_minute()         # start the next scan
            self.write_samples_to_file(pkts)
            e.wait()                    # wait for notification from mobilesim to start next scan
            e.clear()
        return
        
    def scan_a_minute(self):
        pkts = []
        blescan.hci_le_set_scan_parameters(sock)
        blescan.hci_enable_le_scan(sock)
        t1 = time.time()
        while True:
            pkts.extend(blescan.parse_events(sock, 10))  #parse needed packets in blescan
            if time.time - t1 > 60:
                break
        blescan.hci_disable_le_scan(sock)
        return pkts
        
    def write_samples_to_file(self,pkts):
        sorted_pkts = sorted(pkts, key=lambda x: x['TS'])
        t = int(sorted_pkts[0][TS])
        samples_this_second = {}
        f = open("mysamples.txt","w")
        for p in sorted_pkts:
            if p['TS'] > t:
                # a new second
                for minor,rssi in samples_this_second.iteritems():
                   pktTemplate["Beacon"] += [{{"RSSIs":rssi,"UUID":ORGID,"Minor":minor,"Major":"0","TxPower":100}}]
                f.write(json.dumps(pktTemplate)+"\n")
                samples_this_second = {}
                t = int(p['TS'])
            else:
                samples_this_second[p['MINOR']] += [p['RSSI']]
        # last second
        for minor,rssi in samples_this_second.iteritems():
           pktTemplate["Beacon"] += [{{"RSSIs":rssi,"UUID":ORGID,"Minor":minor,"Major":"0","TxPower":100}}]
        f.write(json.dumps(pktTemplate)+"\n")
        f.close()
        return


class mobilesim(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        return
        
    def run(self):
        e.wait()    # for the very first launch, wait until rpscan is ready for a minute date
        e.clear()
        while True:
            print "launch mobilesim"
            # todo: call to launch mobilesim, blocking call, continue after it finishes
            e.set() # notify rpscan that mobilesim is finished so that it can start next scan
            # continue to relauch mobilesim which reads in the refreshed samples file
            # mobilesim takes longer to init, so there is a 20 seconds gap in between
        return

t = rpscan()
t.start()
t = mobilesim()
t.start()


