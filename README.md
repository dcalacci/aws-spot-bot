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




### Creating a Lab Config

All labbox configuration files are python files stored in `~/.lab_config`. The
config for a lab named `my-lab` would be stored at `~/.lab_config/my-lab.py`.

You can list all available configs by running:

```
labbox config ls
```

To create a new configuration named `my-lab`, run:

```
labbox config new my-lab --from_existing default
```

the `--from_existing` flag specifies if you'd like to copy an existing config.
Running this command without the flag automatically copies the default config.

To edit your new config in your editor, run: 

```
labbox config edit my-lab
```

Go through the example configuration below, and make sure your new configuration
has sensible values for all the variables.

#### Config Variables

Here is an example configuration file, annotated. All of these variables
**must** be defined for each Labbox config!
```python
# ================= Project Specific Config ===========
GROUP_NAME = "default" # string, name for the lab

# list of directories to exclude when making a code archive
ARCHIVE_EXCLUDES = ["R-drake"]

# URL of the S3 bucket to use when creating a code archive
S3_BUCKET = "s3://mixing"

# SSH username for the AWS instance. Almost always `ubuntu`
SSH_USER_NAME = "ubuntu"

# Local path to your AWS key
PATH_TO_KEY = "~/attic/aws_2/dan.pem"

# Relative path from your project root (where you will run the labbox commands)
# to your "data directory"
DATA_DIR = "../data"

# Relative path for directory where data processing output goes
OUTPUT_DIR = "output"

# =============== Default configs ==================
# Regions to examine
AWS_REGIONS = ['us-east-2']
# Labbox caches availability zone scans. This is the expiration time of that
# cache. Set it lower to keep your availability zone info up to date
AZ_PICKLE_EXPIRE_TIME_DAYS = 30

# Expiration time for spot pricing information scraped from AWS. Set lower to
# always have more up to date spot pricing info.
SPOT_PRICING_PICKLE_EXPIRE_SEC = 30 * 60


# =============== Personal config ==================
KEY_NAME = "dan"

# The AMI you use that must be available in every region must have a name.
# Labbox uses this name to find and launch your AMI.
AMI_NAME = 'lab-in-a-box'

# List of Instancetypes to use for calculating spot pricing.

# Labbox will use the first element of this list when choosing what instance
# type to launch.
INSTANCE_TYPES = ['r4.8xlarge']
# maximum bid for your spot request
BID = 0.8
# how many instances to launch. Right now usage is only defined for 1.
QTY_INSTANCES = 1
# how long to wait when requesting a server before Labbox decides it's timed
# out.
SERVER_TIMEOUT = 60 * 5

WAIT_FOR_HTTP = True
WAIT_FOR_SSH = True
OPEN_IN_BROWSER = True
OPEN_SSH = True
ADD_TO_ANSIBLE_HOSTS = True
RUN_ANSIBLE = True
COPY_CODE = True
```


### Launching a Lab and syncing data

After creating a configuration, you can request a spot instance with your
specified AMI using:

```
labbox launch --from-config my-lab
```
This will:

- Find the availability zone & region with the best "score" (based on mean price
  and variance) for the instance type specified in your config.
- Upload your current directory's code to the S3 bucket specified by
  `S3_BUCKET`
- Download that code archive to the remote machine
- Move it to the `rstudio` users' home directory
- Set the security group to accept ports `80` and `22`
- Launch an SSH session into the instance
- Launch a web browser into the instance

TO make sure your instance has your code uploaded, you can run:

```
labbox run my-lab 0 rsync
```

The `0` is a placeholder right now. In the future I hope Labbox will support
multiple instances, but for now it just handles one -- so you must specify `0`
as the "instance ID"

#### Syncing Data

Syncing data is a command that's run separately (since it often takes a while).
To do this, run:

```
labbox data my-lab 0 sync data
```

If you change data on the remote machine and want to sync back to your local
box, you can run the sync command with the `--pull` flag:

```
labbox data my-lab 0 sync data --pull
```

##### Output
I often have a separate directory for "output" of my analysis, different from my
raw data directory. This directory's location is specified by the `OUTPUT_DIR`
config variable. You sync it in the same way you sync the data directory:

```
labbox data my-lab 0 sync output

# and to pull data
labbox data my-lab 0 sync output --pull
```

### Connecting and updating code on the instance

To ssh into your instance, you can run:

```
labbox run my-lab 0 ssh
```

To open your instance in a browser, you can run:

```
labbox run my-lab 0 browser
```

### Workflow
So far, working with labbox looks like this:

- I realize there's a command or analysis I need to run that takes a lot of RAM
- I run:
```
cd path/to/project/root
labbox launch --from-config my-lab
labbox run my-lab 0 rsync
labbox data my-lab 0 sync data
labbox data my-lab 0 sync output
labbox run my-lab 0 ssh
```

I do whatever processing I need to do. If I'm running Rstudio or Jupyter on the
instance, I run `labbox run my-lab 0 browser`.

After the processing is done, I sync data changes. My projects are structured in
such a way that I usually never alter the raw data (the "data" directory), so I
usually just have to pull output:

```
labbox data my-lab 0 sync output --pull
```

If I've made any code changes on the server, I also run `labbox run my-lab 0 rsync`

### Ansible
For convenience Ansible is integrated into this tool. This allows one to
automatically run tasks on the servers after they are launched. This saves one
from needing to rebuild AMIs every time a change is required. See
`user_config.py` and `main.py` for more details. Be warned that hosts are not
automatically removed from the Ansible `hosts` file.


### DISCLAIMER!!
This library is something I threw together for my personal use. The code is not
well tested and is in no way production worthy. Feel free to contribute.


### License
MIT
