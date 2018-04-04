#!/usr/bin/env python

from __future__ import print_function

from argparse import ArgumentParser, Action

import boto.ec2
import os

# regions = ['us-west-2', 'us-east-1', 'us-west-1', 'eu-west-1', 'sa-east-1',
#             'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1', 'eu-central-1']

regions = [
"eu-west-3",
"eu-west-2",
"eu-west-1",
"ap-northeast-2",
"ap-northeast-1",
"sa-east-1",
"ca-central-1",
"ap-southeast-1",
"ap-southeast-2",
"eu-central-1",
"us-east-1",
"us-east-2",
"us-west-1",
"us-west-2"]

def main():

    parser = ArgumentParser(
        'aws_ami_copier.py',
        description="Tool to copy an ami image to all of the regions."
    )

    parser.add_argument(
        '-aws-access-key', required=True,
        action=EnvDefault, envvar='AWS_ACCESS_KEY',
        help='AWS Access Key (or AWS_ACCESS_KEY environment variable)'
    )
    parser.add_argument(
        '-aws-secret-key', required=True,
        action=EnvDefault, envvar='AWS_SECRET_KEY',
        help='AWS Secret Key (or AWS_SECRET_KEY environment variable)'
    )

    parser.add_argument(
        '-ami', required=True,
        action=EnvDefault, envvar='AMI',
        help='AMI to copy (or AMI environment variable)'
    )

    parser.add_argument(
        '-image_type', required=True,
        action=EnvDefault, envvar='IMAGE_TYPE',
        help='Image type e.g. centos or ubuntu (or IMAGE_TYPE environment variable)'
    )

    parser.add_argument(
        '-region', required=True,
        action=EnvDefault, envvar='REGION',
        help='Region to copy from (or REGION environment variable)'
    )

    opts = parser.parse_args()
    #print(opts)
    _copy_to_all_the_regions(opts.ami, opts.image_type, opts.region, 
                            opts.aws_access_key, opts.aws_secret_key)

def _copy_to_all_the_regions(ami, type_of_image, origin_region, 
                            aws_access_key, aws_secret_key):

    for region in regions:
        if region is not origin_region.lower():
            conn = boto.ec2.connect_to_region(region,
                                      aws_access_key_id=aws_access_key,
                                      aws_secret_access_key=aws_secret_key)

            if conn:
                image = conn.copy_image(origin_region, ami)
                print(region, type_of_image, image.image_id)
            else:
                print("Could not connect to region...")

# http://stackoverflow.com/questions/10551117/setting-options-from-environment-variables-when-using-argparse
class EnvDefault(Action):
    """
    Inspects the environment for a variable
    before looking for a command line value
    """
    def __init__(self, envvar, required=True, default=None, **kwargs):
        if not default and envvar:
            if envvar in os.environ:
                default = os.environ[envvar]
        if required and default:
            required = False
        super(EnvDefault, self).__init__(default=default, required=required,
                                         **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)

if __name__ == '__main__':
    main()
