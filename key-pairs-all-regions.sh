#!/usr/bin/env bash
# author: dcalacci@media.mit.edu
# key-pairs-all-regions.sh
# copies a private key file to all regions on AWS

AWS_REGION=$(aws ec2 describe-regions --output text | awk '{print $3}' | xargs)

ssh-keygen -y -f $1 > /tmp/aws.pub

for each in ${AWS_REGION}
do
    echo "Region: $each"
    aws ec2 import-key-pair --key-name dan --public-key-material file:///tmp/aws.pub --region $each;
done
