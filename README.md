# Labbox
Ever have a script or data pipeline you need to run on a remote machine? Ever
wish you could just run your existing code on that machine, data and all? Don't
want to do the "right thing" and use Docker? Well hey, you've come to the right place.

## What it does

This will find the cheapest availability zone on AWS for an instance type you
give it, launch a specified AMI in that availability zone, copy your current
code and data directory to the machine, and automatically put you in an ssh
session and browser session.

I most often use it with this AMI: 


## How it chooses an availability zone

It ranks them by price and price variance, so your instance is less likely to
get shut down by changes in demand.

## Usage

There are a few things you need to do to get started, but thankfully I've made a
bunch of scripts to make it easy.

### Installation & Prep

To install, run:

```
python setup.py
```


1. First, make sure your default AWS credentials work ok by running:

```
aws configure
```

2. Pick an AMI. Use a public one, make your own, whatever. Then, to make sure
   your AMI is available in all regions, run the following:

```
aws-ami-copy -aws-access-key [...] -aws-secret-key [...] -ami [YOUR AMI ID HERE] -image_type [ubuntu, etc] -region [region ID]
```

3. To make sure you have key access in all regions, run this to spread your key around:

This will generate your public key, copy it to a temporary file, and import the
key pair to all available regions.

```
key-pairs-all-regions.sh /path/to/private/key.pem
```




### Usage
Edit `user_config.py` to your specifications then run `main.py`.   

### Ansible
For convenience Ansible is integrated into this tool. This allows one to
automatically run tasks on the servers after they are launched. This saves one
from needing to rebuild AMIs every time a change is required. See
`user_config.py` and `main.py` for more details. Be warned that hosts are not
automatically removed from the Ansible `hosts` file.


### DISCLAIMER!!
This library is something I threw together for my personal use. The code is not
well tested and is in no way production worthy. Feel free to contribute.


### Requested contributions
- add a check to report how many instances you currently have running
- add to pypy
- search the project for "todo" and improve those items


### License
MIT
