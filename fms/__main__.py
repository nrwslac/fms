import sys, argparse, json
from happi import Client
from .utils import TypeEnforcer as te
from happi.item import OphydItem
from happi.errors import EnforceError
from .happi.containers import FMSRaritanItem, FMSBeckhoffItem, FMSSRCItem
from typing import List
from .check_topology import check_topology
from .grafana import fetch_alert, create_alert_rule, delete_alert_rule, fetch_alert_group, update_alert_rule
from .serialize_alert import ProvisionedAlertRule, AlertGroup
from apischema import serialize
from .create_alert import AlertCreater

fms_happi_database = "fms_test.json"

def create_alert(value, title, folder_name, rule_group, polarity, pv, happi_name):
    ac = AlertCreater()
    if polarity == None:
        ac.create_alert(
            value,
            alert_title=title,
            folder_name=folder_name,
            rule_group=rule_group,
            pv=pv,
            happi_name=happi_name)
    else:
        ac.create_alert("A new alert test")

def delete_alert(alert_uid):
    delete_alert_rule(alert_uid)

def update_alert(alert_uid):
    alert = fetch_alert(alert_uid)
    alert_rule = ProvisionedAlertRule.parse_raw(alert)

    #alert_rule.title = alert_rule.title + "TEST"
    alert_rule.for_ = "2m"
    #alert_rule.labels = dict(subsystem="fmsv2")

    update_alert_rule(alert_uid, json.dumps(alert_rule.dict(by_alias=True)))

def get_alert_group(folder_uid, group):
    #print(group)
    alert_group = fetch_alert_group(folder_uid, group) 
    #print(alert_group)
    alert = AlertGroup.parse_obj(alert_group)
    print(alert) 

def get_alert(alert_uid):
    alert = fetch_alert(alert_uid)
    alert_rule = ProvisionedAlertRule.parse_raw(alert)
    #print(alert_rule)
    print(f'******* the rule:{alert_rule}')
    for query in alert_rule.data:
        print(f"------------{query}------------\n")

        #print(f"query ID: {query.refId}")
        #print(f"*********************{query.model.conditions}*******************")
        #print(f"model type: {query.model.type_}")
        #print(f"model functions: {query.model.functions}")
    #print(f"writing alert to file: {alert}")
    #with open("sample_alert.json", "w") as f:
    #    f.write(alert)


def find_port(name, client=None):
    if client == None:
        client = Client(path=fms_happi_database)
    item = client.find_item(name=name)
    return item.root_sensor_port

def delete_sensor(sensor_name, client=None):
    if client == None:
        client = Client(path=fms_happi_database)
    item = client.find_item(name=sensor_name)

    if type(item) == FMSRaritanItem:
        parent_switch_item = client.find_item(name=item.parent_switch)
        port = "port" + str(item.root_sensor_port)
        sensor_list = getattr(parent_switch_item, port)
        print(f"current list to delete from: {sensor_list}")
        sensor_list = [sensor for sensor in sensor_list if sensor[0] != sensor_name]
        print(f"deleted: {sensor_name} from: {sensor_list}")
        setattr(parent_switch_item, port, sensor_list)
        parent_switch_item.save()

    client.remove_item(item)

def validate():
    client = Client(path=fms_happi_database)
    results = client.validate()
    if len(results) == 0:
        print("Success! Valid FMS Database.")
    else:
        print(f'This devices are malformed! {results}')


def get_all_src_status():
    get_src_controllers()
def get_src_controllers(client: Client=None) -> List[str]:
    if client is None:
        client = Client(path=fms_happi_database)
    ret = client.search(name='booch')
    print(ret)

def add_src_controller(client=None):
    controller_name = te.get_str("Enter controller name\n")

    if client == None:
        client = Client(path=fms_happi_database)

    item = client.create_item(item_cls=FMSSRCItem,
        name=controller_name,
        prefix="RTD:TEST:FMS"
    )
    item.save()

def add_sensor_to_src(item, client=None):
    if client == None:
        client = Client(path=fms_happi_database)

    src_controller = client.find_item(name=item.parent_switch)

    port = None
    if item.root_sensor_port != None:
        #root sensor
        curr_sensor_list = []
        port = "port" + item.root_sensor_port
    else:
        port = find_port(item.last_connection_name, client)
        print(f'Saving Port to Current Item: {item.name}')
        item.root_sensor_port = port

        port = "port" + str(port)
        curr_sensor_list = getattr(src_controller, port)                
        print(f'Current List: {curr_sensor_list}')

    curr_sensor_list.append((item.name, item.eth_dist_last))
    print(f'Updated List: {curr_sensor_list}')

    setattr(src_controller, port, curr_sensor_list)
    src_controller.save()

def add_fms_sensor(sensor_name=None, client=None):
    container_type = None
    root_sensor_port = None
    eth_dist_last = None
    if sensor_name == None:
        sensor_name = te.get_str("Enter sensor name\n")
        print(sensor_name)
    sensor_type = te.get_list_str(["Beckhoff", "Raritan"], "Enter sensor type Beckhoff/Raritan\n")
    print(sensor_type)
    sensor_prefix = te.get_str("Enter PV")

    if sensor_type == "Raritan":
        parent_switch = te.get_str("Enter a valid Parent SRC Controller happi name:\n")
        print(parent_switch)
        #validate input here
        root_sensor_port = te.get_str("Enter port number if first sensor or leave blank if not")
        print(f"roote sensor port is: {root_sensor_port}")
        last_connection_name = te.get_str("Enter the happi name of the last sensor this one is attached to\n")
        print(f"last conn {last_connection_name}")
        #validate input here
        eth_dist_last = te.get_int("Enter Eth Distance from last sensor\n")
        print(eth_dist_last)
        container_type = FMSRaritanItem
        if (root_sensor_port == "" or root_sensor_port == None) and (last_connection_name == "" or last_connection_name == None):
            raise(EnforceError("must define root_sensor port or last connection"))
    else:
        container_type = FMSBeckhoffItem
    
    if client == None:
        client = Client(path=fms_happi_database)

    item = client.create_item(item_cls=container_type,
        name=sensor_name,
        prefix=sensor_prefix,
        parent_switch=parent_switch,
        root_sensor_port=root_sensor_port,
        eth_dist_last=eth_dist_last,
        last_connection_name=last_connection_name
    )
    if type(item) == FMSRaritanItem:
        ret = add_sensor_to_src(item, client)
    item.save()

def SetupArgumentParser():
    parser = argparse.ArgumentParser(
                        prog="fms",
                        description='A module for managing facillity monitoring devices',
                        epilog='Thank you for using the fms CLI!')
    parser.add_argument('--validate', action='store_true', dest="validate", help='validate database')
    parser.add_argument('--add_sensor', dest="add_sensor", help='walk through adding a sensor to FMS')
    parser.add_argument('--add_src_controller', action='store_true', dest="add_src_controller", help='walk through adding a raritan SRC controller to FMS')
    parser.add_argument('-s','--src', dest='src_controller', help='src controller')
    parser.add_argument('-p','--port', dest='port', help='src controller port')

    parser.add_argument('--list_all_sensors', action='store_true', help="print a list of sensors")
    parser.add_argument('--check_topology', action='store_true', dest='check_topology', help='print the current FMS topology')
    parser.add_argument('--launch_nalms', action='store_true',help="launch the nalms home screen")
    parser.add_argument('--delete_sensor', dest='delete_sensor', help="delete_sensor")
    
    parser.add_argument('-t','--alert_title', dest='alert_title', help='name of alert rule')
    parser.add_argument('-f','--folder', dest='folder_name', help='grafana alert folder name')
    parser.add_argument('-r','--rule_g', dest='rule_group', help='name of alert rule group')
    parser.add_argument('-v','--thresh', dest='thresh_value', help='alert trip point')
    parser.add_argument('-pl','--polarity', dest='polarity', help='alert high or low', choices=["gt", "lt"], default=None)
    parser.add_argument('-pv','--pv', dest='prefix', help='epics PV', default=None)
    parser.add_argument('-hn','--happi_name', dest='happi_name', help='happie database name', default=None)


    parser.add_argument('--get_alert', action='store_true', help='alert rule id to GET')
    parser.add_argument('--get_alert_group', action='store_true', help='alert rule group')
    parser.add_argument('--update_alert', action='store_true', help='alert rule group')
    parser.add_argument('-a','--aid', dest='alert_id', help='alert uid')

    parser.add_argument('--create_alert', action='store_true', help='create alert rule')
    parser.add_argument('--delete_alert', action='store_true', help='delete alert rule')
    return parser

def main(argv):
    argument_parser = SetupArgumentParser()
    options = argument_parser.parse_args()
    if options.add_sensor:
        add_fms_sensor(options.add_sensor)
    elif options.add_src_controller:
        add_src_controller()
    elif options.validate:
        validate() 
    elif options.check_topology:
        check_topology(options.src_controller, options.port)
    elif options.delete_sensor:
        delete_sensor(options.delete_sensor)
    elif options.get_alert:
        get_alert(options.alert_id)
    elif options.create_alert:
        create_alert(
            options.thresh_value,
            options.alert_title,
            options.folder_name,
            options.rule_group,
            options.polarity,
            options.prefix,
            options.happi_name
        ) 
    elif options.delete_alert:
        delete_alert(options.alert_id) 
    elif options.get_alert_group:
        get_alert_group(options.folder_name, options.rule_group) 
    elif options.update_alert:
        update_alert(options.alert_id) 
    else:
        argument_parser.print_help()

main(sys.argv)

#python -m fms --create_alert -t flood11 -f xrt -r xrt_pcw -v 0 -pv MR1K1:BEND:MMS:XUP.RBV