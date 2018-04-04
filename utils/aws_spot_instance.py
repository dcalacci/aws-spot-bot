import os
import random
import time
import webbrowser
import socket
import datetime
import subprocess
import json
import boto3

from .. import configs
from configs import default as uconf
from os.path import expanduser
from .aws_spot_exception import SpotConstraintException
from . import paths

# class MyEncoder(json.JSONEncoder):
#     def default(self, obj):
#         if not isinstance(obj, Tree):
#             return super(MyEncoder, self).default(obj)

class MyEncoder(json.JSONEncoder):
        def default(self, o):
            print(o)
            try:
                return o.__dict__
            except:
                return None

def from_json(conf, n):
    path = os.path.join(paths._custom_path(),
                        "instances",
                        "{}_{}.json".format(conf, n))
    with open(path, 'r') as f:
            s = json.load(f)
    random_id,az_zone,region, instance_type,ip, bid, ami_id,key_name, security_group_id,security_group_name,group_name, spot_instance_request_id,instance_id, ip, config_name = s

    si = AWSSpotInstance(region,
                         az_zone,
                         instance_type,
                         ami_id,
                         uconf.BID,
                         config_name)
    si.random_id = random_id
    si.security_group_id = security_group_id
    si.security_group_name = security_group_name,
    si.spot_instance_request_id = spot_instance_request_id
    si.instance_id = instance_id
    si.ip = ip
    print(">> created instance with ip: ", si.ip, ip)
    si.start_boto()
    return si


# TODO: make an easy serialization of this object to save
# and then use later to destroy, run commands on, etc.
class AWSSpotInstance():

    def __init__(self, region, az_zone, instance_type, ami_id, bid, config_name):
        uconf = paths._load_config(config_name)
        self.config_name = config_name
        self.random_id = str(random.random() * 1000)
        self.az_zone = az_zone
        self.region = region
        self.instance_type = instance_type
        self.ip = None
        self.bid = bid
        self.ami_id = ami_id
        self.key_name = uconf.KEY_NAME
        self.security_group_id = uconf.SECURITY_GROUP_ID
        self.security_group_name = uconf.SECURITY_GROUP_NAME
        self.GROUP_NAME = uconf.GROUP_NAME

        # == Boto3 related tools ==
        boto3.setup_default_session(region_name=self.region)
        self.client = boto3.client('ec2')
        session = boto3.session.Session(region_name=self.region)
        self.ec2_instance = session.resource('ec2')

        self.group_name = uconf.GROUP_NAME

        # == Values that we need to wait to get from AWS ==
        self.spot_instance_request_id = None
        self.instance_id = None
        self.status_code = None
        self.ip = None

    def serialize(self, n):
        self.serializable = [self.random_id, self.az_zone,
                             self.region, self.instance_type,
                             self.ip, self.bid, self.ami_id,
                             self.key_name, self.security_group_id,
                             self.security_group_name,
                             self.group_name, self.spot_instance_request_id,
                             self.instance_id, self.ip, self.config_name]
        instances_path = os.path.join(paths._custom_path(),
                                      "instances")
        if not os.path.exists(instances_path):
            os.mkdir(instances_path)
        path = os.path.join(instances_path,
                            "{}_{}.json".format(self.group_name, n))
        with open(path, 'w') as f:
            json.dump(self.serializable, f)

    def start_boto(self):
        boto3.setup_default_session(region_name=self.region)
        self.client = boto3.client('ec2')
        session = boto3.session.Session(region_name=self.region)
        self.ec2_instance = session.resource('ec2')

    def request_instance(self):
        """Boots the instance on AWS"""
        print(">> Requesting instance, key name: {}".format(self.key_name))
        print(">> Region: ", self.region)
        response = self.client.request_spot_instances(
            SpotPrice=str(self.bid),
            ClientToken=self.random_id,
            InstanceCount=1,
            Type='one-time',
            ValidUntil=datetime.datetime.utcnow() + datetime.timedelta(seconds=60 * 100),
            LaunchSpecification={
                'ImageId': self.ami_id,
                'KeyName': self.key_name,
                'InstanceType': self.instance_type,
                'Placement': {
                    'AvailabilityZone': self.az_zone,
                },
                'EbsOptimized': False,
                # 'SecurityGroupIds': [
                #     self.security_group_id
                # ]
            }
        )
        self.spot_instance_request_id = response.get('SpotInstanceRequests')[0].get('SpotInstanceRequestId')
        print(response.get("SpotInstanceRequests")[0])
        return response

    def get_spot_request_status(self):
        print(">> Checking instance status")
        response = self.client.describe_spot_instance_requests(
            SpotInstanceRequestIds=[self.spot_instance_request_id],
        )
        self.status_code = response.get('SpotInstanceRequests')[0].get('Status').get('Code')
        self.instance_id = response.get('SpotInstanceRequests')[0].get('InstanceId')
        return {'status_code': self.status_code, 'instance_id': self.instance_id}

    def cancel_spot_request(self):
        print(">> Cancelling spot request")
        response = self.client.cancel_spot_instance_requests(
            SpotInstanceRequestIds=[self.spot_instance_request_id],
        )
        return response


    def open_http_and_ssh(self):
        from . import security_groups as sg
        print(">> Altering security group to allow ssh and http access")

        rules = [
            sg.SecurityGroupRule("tcp", 80, 80, "0.0.0.0/0", None),
            sg.SecurityGroupRule("tcp", 22, 22, "0.0.0.0/0", None)
        ]
        instance = self.ec2_instance.Instance(self.instance_id)
        ip = instance.public_ip_address
        #self.security_groups = self.ec2_instance.Instance(self.instance_id).groups

        self.vpc = self.ec2_instance.Vpc(instance.vpc_id)
        group = sg.get_or_create_security_group(
            self.client,
            self.security_group_name,
            vpc_id=self.vpc.vpc_id)
        sg.update_security_group(self.client,
                                 group,
                                 rules)

    def get_ip(self):
        if self.ip:
            print(">> Have IP: {}".format(self.ip))
            return self.ip

        print(">> No IP, checking status... {}".format(self.ip))
        if not self.status_code:
            self.get_spot_request_status()

        for idx in range(100):
            if not self.instance_id:
                if 'pending' in self.status_code:
                    time.sleep(3)
                    self.get_spot_request_status()
                else:
                    raise SpotConstraintException("Spot constraints can't be met: " + self.status_code)
            else:
                self.ip = self.ec2_instance.Instance(self.instance_id).public_ip_address
                break

        # TODO: improve this
        if not self.ip:
            raise Exception('There is no public IP address for this instance... Maybe the bid failed..')

        return self.ip

    def terminate(self):
        """Terminates the instance on AWS"""
        pass

    def open_ssh_term(self):
        """Opens your default terminal and starts SSH session to the instance"""
        # TODO. This wont work on non osx machines.
        uconf = paths._load_config(self.group_name)
        cmd = ["tmux", "-c", "ssh -i {} {}@{}".format(uconf.PATH_TO_KEY,uconf.SSH_USER_NAME, self.get_ip())]
        print(">> connecting using: ", cmd)
        subprocess.call(cmd)
        #appscript.app('Terminal').do_script('ssh ' + uconf.SSH_USER_NAME + '@' + self.get_ip())

    def open_in_browser(self, port='80'):
        """Opens the instance in your browser to the specified port.
        Default port is Jupyter server
        """
        webbrowser.open_new_tab('http://' + self.ip + ':' + port)

    def add_to_ansible_hosts(self):
        home = expanduser("~")
        path = "{}/.lab_configs/ansible".format(home)
        with open(os.path.join(path, '{}_hosts'.format(self.GROUP_NAME)), 'a') as file:
            file.write(str(self.ip) + '\n')

    def wait_for_http(self, port=80, timeout=uconf.SERVER_TIMEOUT):
        """Waits until port 80 is open on this instance.
        This is a useful way to check if the system has booted.
        """
        self.wait_for_port(port, timeout)

    def wait_for_ssh(self, port=22, timeout=uconf.SERVER_TIMEOUT):
        """Waits until port 22 is open on this instance.
        This is a useful way to check if the system has booted.
        """
        self.wait_for_port(port, timeout)

    def wait_for_port(self, port, timeout=uconf.SERVER_TIMEOUT):
        """Waits until port is open on this instance.
        This is a useful way to check if the system has booted and the HTTP server is running.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start = datetime.datetime.now()
        print(">> waiting for port", port)

        if not self.get_ip():
            raise Exception("Error getting IP for this instance. Instance must have an IP before calling this method.")

        print(">> Creating security group in VPC...")
        self.open_http_and_ssh()

        while True:
            # We need this try block because depending on the parameters the system will cause the connection
            # to timeout early.
            try:
                if sock.connect_ex((self.get_ip(), port)):
                    # we got a connection, lets return
                    return
                else:
                    time.sleep(3)
            except:
                # TODO: catch the timeout exception and ignore that, but every other exception should be raised
                # The system timeout, no problem
                pass

            if (datetime.datetime.now() - start).seconds > timeout:
                print((datetime.datetime.now() - start).seconds)
                raise Exception("Connection timed out. Try increasing the timeout amount, or fix your server.")

        print(">> port %s is live" % (port))

if __name__ == '__main__':
    import pricing_util
    # best_az = pricing_util.get_best_az()
    # print best_az.region
    # print best_az.name
    region = 'us-east-1'
    az_zone = 'us-east-1d'
    instance_type = uconf.INSTANCE_TYPES[0]
    si = AWSSpotInstance(region, az_zone, instance_type, uconf.AMI_ID, uconf.BID)
    response = si.request_instance()
    print(response)
    print(si.get_ip())
    si.wait_for_ssh()
    si.wait_for_http()

    si.open_in_browser()
    si.open_ssh_term()
