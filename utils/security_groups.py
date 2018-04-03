import boto3
import collections

# from https://gist.github.com/steder/1498451
SecurityGroupRule = collections.namedtuple("SecurityGroupRule", ["ip_protocol",
                                                                 "from_port",
                                                                 "to_port",
                                                                 "cidr_ip",
                                                                 "src_group_name"])

def get_or_create_security_group(c, group_name,
                                 vpc_id=None,
                                 description=""):
    """
    """
    groups = c.describe_security_groups(
        Filters=[{'Name': 'group-name',
                  'Values': [group_name]}])['SecurityGroups']
    ec2 = boto3.resource('ec2')
    group = ec2.SecurityGroup(groups[0]['GroupId']) if groups else None
    #group = c.SecurityGroup(r['GroupId'])
    if not group:
        print(">> Creating Group {} for vpc {}".format(group_name, vpc_id))
        if vpc_id is not None:
            r = ec2.create_security_group(
                GroupName=group_name,
                VpcId=vpc_id,
                Description="A group for {}".format(group_name))
        else:
            print(">> Creating Group {} for vpc {}".format(group_name, vpc_id))
            r = ec2.create_security_group(
                GroupName=group_name,
                VpcId=vpc_id,
                Description="A group for {}".format(group_name))
        group = ec2.SecurityGroup(r['GroupId'])
    return group


def modify_sg(c, group, rule, authorize=False, revoke=False):
    src_group = None
    if rule.src_group_name:
        src_group = c.describe_security_groups(
            Filters=[{'Name': 'group-name',
                      'Values': [rule.src_group_name]}])['SecurityGroups'][0]

    if authorize and not revoke:
        print("Authorizing missing rule %s..."%(rule,))
        group.authorize_ingress(
            FromPort = rule.from_port,
            ToPort = rule.to_port,
            CidrIp = rule.cidr_ip,
            IpProtocol = rule.ip_protocol)

def authorize(c, group, rule):
    """Authorize `rule` on `group`."""
    return modify_sg(c, group, rule, authorize=True)


def revoke(c, group, rule):
    """Revoke `rule` on `group`."""
    return modify_sg(c, group, rule, revoke=True)


def update_security_group(c, group, expected_rules):
    """
    """
    print('Updating group "%s"...'%(group.group_name,))
    import pprint
    print("Expected Rules:")
    pprint.pprint(expected_rules)

    current_rules = []
    for rule in group.ip_permissions:
        # if not rule.grants[0].cidr_ip:
        current_rule = SecurityGroupRule(rule['IpProtocol'],
                                         rule['FromPort'],
                                         rule['ToPort'],
                                         "0.0.0.0/0",
                                         None)
        # else:
        #     current_rule = SecurityGroupRule(rule.ip_protocol,
        #                       rule.from_port,
        #                       rule.to_port,
        #                       rule.grants[0].cidr_ip,
        #                       None)

        # if current_rule not in expected_rules:
        #     revoke(c, group, current_rule)
        # else:
        current_rules.append(current_rule)

    print("Current Rules:")
    pprint.pprint(current_rules)

    for rule in expected_rules:
        if rule not in current_rules:
            authorize(c, group, rule)


def create_security_groups():
    """
    attempts to be idempotent:
    if the sg does not exist create it,
    otherwise just check that the security group contains the rules
    we expect it to contain and updates it if it does not.
    """
    c = boto.connect_ec2()
    for group_name, rules in SECURITY_GROUPS:
        group = get_or_create_security_group(c, group_name)
        update_security_group(c, group, rules)
