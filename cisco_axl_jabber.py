# -*- coding: utf-8 -*-
#!/usr/bin/python3
import sys
from zeep import Client
from zeep.cache import SqliteCache
from zeep.transports import Transport
from zeep.exceptions import Fault
from zeep.plugins import HistoryPlugin
from requests import Session
from requests.auth import HTTPBasicAuth
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from lxml import etree
from influxdb import InfluxDBClient
import argparse
import os
import datatime

os.nice(20)

parser = argparse.ArgumentParser()

def build_json(name, devicepool):
    dUTC = datetime.datetime.utcnow()
    
    json_body = {
        'measurement': 'jabber_status',
        'tags': {
            'name': name,
            'devicepool': devicepool,
            'unifiedcm':'Unknown',
            'status' : 'Unknown',
            'statusreason': 'Unknown',
            'activeloadid': 'Unknown'
        },
        'time': dUTC,
        'fields': {
            'loginuserid': 'Unknown',
            'ipaddress': 'Unknown'
        }
    }
        
    return json_body
    

# main function
def main(CUCM_ADDRESS,USERNAME,PASSWORD,VERSION):
    # Common Plugins
    history = HistoryPlugin()

    # Build Client Object for AXL Service
    # The WSDL is a local file in the working directory, see README
    axl_wsdl = 'schema/' + VERSION + '/AXLAPI.wsdl'
    axl_location = f'https://{CUCM_ADDRESS}:8443/axl/'
    axl_binding = '{http://www.cisco.com/AXLAPIService/}AXLAPIBinding'

    axl_session = Session()
    axl_session.verify = False
    axl_session.auth = HTTPBasicAuth(USERNAME, PASSWORD)

    axl_transport = Transport(cache=SqliteCache(), session=axl_session,
                              timeout=20)
    axl_client = Client(wsdl=axl_wsdl, transport=axl_transport,
                        plugins=[history])
    axl_service = axl_client.create_service(axl_binding, axl_location)

    # Build Client Object for RisPort70 Service
    wsdl = f'https://{CUCM_ADDRESS}:8443/realtimeservice2/services/RISService70?wsdl'
    session = Session()
    session.verify = False
    session.auth = HTTPBasicAuth(USERNAME, PASSWORD)
    transport = Transport(cache=SqliteCache(), session=session, timeout=20)
    history = HistoryPlugin()
    client = Client(wsdl=wsdl, transport=transport, plugins=[history])
    factory = client.type_factory('ns0')

    def show_history():
        for hist in [history.last_sent, history.last_received]:
            print(etree.tostring(hist["envelope"],
                                 encoding="unicode",
                                 pretty_print=True))


    # Get List of Phones to query via AXL
    # (required when using SelectCmDeviceExt)
    try:
        csfresp = axl_service.listPhone(searchCriteria={'name': 'CSF%'},
                                     returnedTags={'name': '','devicePoolName':''})
        tctresp = axl_service.listPhone(searchCriteria={'name': 'TCT%'},
                         returnedTags={'name': '','devicePoolName':''})
        botresp = axl_service.listPhone(searchCriteria={'name': 'BOT%'},
                         returnedTags={'name': '','devicePoolName':''})
        tabresp = axl_service.listPhone(searchCriteria={'name': 'TAB%'},
                         returnedTags={'name': '','devicePoolName':''})
                                    
    except Fault:
        show_history()
        raise

    # Build item list for RisPort70 SelectCmDeviceExt
    items = []
    # Build item list for output
    points = []
    
    for phone in csfresp['return'].phone:
        items.append(factory.SelectItem(Item=phone.name))
        points.append(build_json(phone.name,phone.devicePoolName['_value_1']))
    for phone in tctresp['return'].phone:
        items.append(factory.SelectItem(Item=phone.name))
        points.append(build_json(phone.name,phone.devicePoolName['_value_1']))
    for phone in botresp['return'].phone:
        items.append(factory.SelectItem(Item=phone.name))
        points.append(build_json(phone.name,phone.devicePoolName['_value_1']))
    for phone in tabresp['return'].phone:
        items.append(factory.SelectItem(Item=phone.name))
        points.append(build_json(phone.name,phone.devicePoolName['_value_1']))
        
    # Lets break this down in chunks of 1000 for RisPort throttling
    chunks = [items[x:x + 1000] for x in range(0, len(items), 1000)]
    
    print("Breaking down into chunks: " + str(len(chunks)) )
    
    for index, chunk in enumerate(chunks):
        print("Processing " + str(index + 1) + " batch..." )
        Item = factory.ArrayOfSelectItem(chunk)

        # Run SelectCmDeviceExt
        criteria = factory.CmSelectionCriteria(
            MaxReturnedDevices = 1000,
            DeviceClass='Phone',
            Model=255,    #255 for all
            Status='Any',
            NodeName='',
            SelectBy='Name',
            SelectItems=Item,
            Protocol='Any',
            DownloadStatus='Any'
        )
        
        StateInfo = ''
        
        try:
            resp = client.service.selectCmDeviceExt( CmSelectionCriteria=criteria, StateInfo=StateInfo )
        except Fault:
            show_history()
            raise

        CmNodes = resp.SelectCmDeviceResult.CmNodes.item
        for CmNode in CmNodes:
            if len(CmNode.CmDevices.item) > 0:
                # If the node has returned CmDevices, save to the points to
                # later compare
                for item in CmNode.CmDevices.item:
                    # Search the results from AXL and update with Risport Info
                    d = next((search for search in points if search["tags"]["name"] == item.Name), None)
                    
                    d['tags']['unifiedcm'] = CmNode.Name
                    d['tags']['status'] = item.Status
                    d['tags']['statusreason'] = item.StatusReason
                    d['tags']['activeloadid'] = item.ActiveLoadID
                    ipaddresses = item.IPAddress
                    ipaddress = ipaddresses['item'][0]['IP']                    
                    d['fields']['ipaddress'] = ipaddress
                    d['fields']['loginuserid'] = item.LoginUserId

        
    try:
        client = InfluxDBClient('<INSERT INFLUXDB IP>', 8086, '', '', 'cisco_risport')
        client.write_points(points,batch_size=100000)    
    except Exception as e:
        print(e)

    print("Successfully captured current Risport status.")
    


if __name__ == "__main__":
    disable_warnings(InsecureRequestWarning)
    parser.add_argument( "-ip","--hostname", required=True, help="Cisco AXL Hostname/IP Address" )    
    parser.add_argument("-u", "--username", required=True, help="User name")
    parser.add_argument("-p", "--password", required=True, help="Password")
    parser.add_argument("-v", "--version", required=True, help="Version")

    args = parser.parse_args()
    
    main(args.hostname,args.username,args.password,args.version)
