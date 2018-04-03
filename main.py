import os
import click
import glob
import json
import subprocess
import boto3
import dill as pickle

from os.path import expanduser
import fabric
from fabric.tasks import execute
from fabric.api import hosts, env
from fabric.context_managers import cd, settings


DEFAULT_EDITOR = '/usr/bin/vi' # backup, if not defined in environment vars

def _open_in_editor(path):
    """open a file in users default editor"""
    path = os.path.abspath(os.path.expanduser(path))
    editor = os.environ.get('EDITOR', DEFAULT_EDITOR)
    subprocess.call([editor, path])

def _check_required_env_vars():
    keys = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "KEY_NAME"]
    in_env = [k in os.environ for k in keys]
#    assert all(in_env), 'Please set the environment variables "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"!'
    return True

if _check_required_env_vars():
    from .utils import pricing_util
    from .utils.aws_spot_instance import AWSSpotInstance, from_json
    from .utils.aws_spot_exception import SpotConstraintException
    from .utils import paths


def _highlight(x, fg='green'):
    if not isinstance(x, str):
        x = json.dumps(x, sort_keys=True, indent=2)
    click.secho(x, fg=fg)

def upload_archive(fpath, name, archive_excludes, s3_bucket, skip_archive):
    import hashlib, os.path as osp, subprocess, tempfile, uuid, sys
    # Archive this package
    thisfile_dir = osp.dirname(osp.abspath(fpath))
    pkg_dir = osp.abspath(osp.join(thisfile_dir, '.'))
    _highlight("Running tar from: {}".format(pkg_dir))
#    assert osp.abspath(__file__) == osp.join(pkg_parent_dir, pkg_subdir, 'deploy2.py'), 'You moved me!'

    # Run tar
#    tmpdir = tempfile.TemporaryDirectory()
    tmpdir = "/tmp"
    if skip_archive:
        _highlight("Skipping archiving, using latest code...")
        # use latest archive
        archives = glob.glob(os.path.join(tmpdir, 'crl_*'))
        if len(archives) == 0:
            _highlight("No existing archives found in {}...".format(tmpdir))
            input("\nPress return to continue and create a new code archive.")
            upload_archive(fpath, name, archive_excludes, s3_bucket, False)
            return
        latest_file = max(archives, key=os.path.getctime)
        local_archive_path = latest_file
    else:
        local_archive_path = osp.join(tmpdir, 'aws_spot_{}.tar.gz'.format(uuid.uuid4()))
        tar_cmd = ["tar", "-vzcf", local_archive_path]
        for pattern in archive_excludes:
            tar_cmd += ["--exclude", '{}'.format(pattern)]
        tar_cmd += ['.']
        _highlight("TAR CMD: {}".format(" ".join(tar_cmd)))

        if sys.platform == 'darwin':
            # Prevent Mac tar from adding ._* files
            env = os.environ.copy()
            env['COPYFILE_DISABLE'] = '1'
            subprocess.check_call(tar_cmd, env=env)
        else:
            subprocess.check_call(tar_cmd)

    # Construct remote path to place the archive on S3
    with open(local_archive_path, 'rb') as f:
        archive_hash = hashlib.sha224(f.read()).hexdigest()
    remote_archive_path = '{}/{}_{}.tar.gz'.format(s3_bucket, name, archive_hash)

    # Upload
    upload_cmd = ["aws", "s3", "cp", local_archive_path, remote_archive_path]
    _highlight(" ".join(upload_cmd))
    subprocess.check_call(upload_cmd)

    # presign_cmd = ["aws", "s3", "presign", remote_archive_path, "--expires-in", str(60 * 60 * 24 * 30)]
    presign_cmd = ["aws", "s3", "presign", remote_archive_path, "--expires-in", str(60 * 60 * 24)]
    _highlight(" ".join(presign_cmd))
    remote_url = subprocess.check_output(presign_cmd).decode("utf-8").strip()
    return remote_url

def _make_download_script(code_url):
    print(">> Downloading code from {}".format(code_url))
    return """
    set -x
    cd ~
    wget -S '{code_url}' -O code.tar.gz
    mkdir research
    cd research
    tar xvaf ../code.tar.gz
    cd ~
    rm code.tar.gz
    sudo mv research /home/rstudio
    sudo usermod -aG ubuntu rstudio
    sudo chmod -R g+rwx /home/rstudio
    sudo chown -R rstudio:ubuntu /home/rstudio/research
    """.format(code_url=code_url)

def get_ami_id_from_name_and_region(name, region):
    boto3.setup_default_session(region_name=region)
    client = boto3.client('ec2')
    amis = client.describe_images()['Images']
    amis = [ami for ami in amis if 'Name' in ami.keys()]
    matches = [ami for ami in amis if ami['Name'] == name]
    if len(matches) > 0:
        return matches[0]['ImageId']
    else:
        return None


def launch_instances(qty, config_name):
    """Launches QTY instances and returns the instance objects."""
    uconf = paths._load_config(config_name)
    best_az = pricing_util.get_best_az()
    launched_instances = []
    print("Best availability zone:", best_az.name)
    print("getting AMI named {} from region {}".format(uconf.AMI_NAME, best_az.region))
    ami_id = get_ami_id_from_name_and_region(uconf.AMI_NAME, best_az.region)
    if ami_id is None:
        print("No AMI Match. Exiting...")
    else:
        print("Found matching AMI with ID {}".format(ami_id))
    for idx in range(qty):
        print('>> Launching instance #{}'.format(idx))
        si = AWSSpotInstance(best_az.region, best_az.name, uconf.INSTANCE_TYPES[0], ami_id, uconf.BID, config_name)
        si.request_instance()
        try:
            si.get_ip()
        except SpotConstraintException as e:
            print(">> ", e.message)
            si.cancel_spot_request()
            continue
        launched_instances.append(si)

    return launched_instances

@click.command()
@click.argument("mname", required=False, default=None)
def ls(mname):
    """List available configs.

    If a configuration name is provided (MNAME), it will print the contents of
    that configuration file.

    """
    if not mname:
        paths._print_all_configurations()
    else:
        if mname in paths._get_config_names():
            with open(os.path.join(configs.__path__[0], "{}.py".format(mname)), 'r') as fin:
                print(fin.read())
        elif mname in paths._get_custom_config_names():
            with open(os.path.join(paths._custom_path(), "{}.py".format(mname)), 'r') as fin:
                print(fin.read())
        else:
            print("No configuration with that name. Available configurations are:")
            paths._print_all_configurations()

@click.command()
@click.argument("mname", required=True)
def edit(mname):
    if mname in paths._get_config_names():
        path = os.path.join(configs.__path__[0], "{}.py".format(mname))
        _open_in_editor(path)
    elif mname in paths._get_custom_config_names():
        path = os.path.join(paths._custom_path(), "{}.py".format(mname))
        _open_in_editor(path)


@click.command()
@click.argument("name", required=True)
@click.option("--from_existing",
              required=False, default="default",
              help="""Name of an existing configuration file to build from. The contents of the
              new configuration file will be the same as the file given here.
              by default, it will pull contents from the 'default'
              configuration, included with this script """)
def new(name, from_existing):
    """ Creates & initializes a new configuration file with the given name. 
    """
    import shutil
    home = expanduser("~")
    if not os.path.exists("{}/.lab_configs".format(home)):
        os.mkdir("{}/.lab_configs".format(home))
    file_to_copy = paths._find_config(from_existing)
    shutil.copyfile(file_to_copy,
                    "{}/.lab_configs/{}.py".format(home, name))


@click.command("edit")
@click.argument("name", required=True)
def edit_ansible(name):
    """Edit the ansible playbook file for the given configuration"""
    import shutil
    if name not in paths._all_config_names():
        return
    ans_path = os.path.join(paths._custom_path(), "ansible")
    if not os.path.exists(ans_path):
        os.mkdir(ans_path)

    path = os.path.join(paths._custom_path(), "ansible/{}.yml".format(name))
    if not os.path.exists(path):
        shutil.copyfile(os.path.join(configs.__path__[0], "../ansible/play.yml"),
                        path)
    print("Saved ansible play to: {}".format(path))
    _open_in_editor(path)

def _run_ansible(conf, tags):
    ans_path = os.path.join(paths._custom_path(),
                            "ansible",
                            "{}.yml".format(conf))
    s = ","
    tags = s.join(tags)
    os.system('ansible-playbook -i {} -s {}.yml --tags "{}"'.format(_find_inventory(conf),
                                                                    ans_path,
                                                                    tags))

@click.command()
@click.argument("conf", required=True)
def from_config(conf):
    """Launches a number of instances with the given configuration file.

    """
    import importlib
    import sys
    uconf = paths._load_config(conf)
    print("Using configuration {}".format(conf))
    #importlib.import_module(conf)
    #uconf = importlib.import_module(conf)
    #_load_module_from_path("uconf", path)
    instances = launch_instances(uconf.QTY_INSTANCES, conf)
    code_url = upload_archive(os.getcwd(), conf, uconf.ARCHIVE_EXCLUDES, uconf.S3_BUCKET, skip_archive=False)

    for n, si in enumerate(instances):
        if uconf.WAIT_FOR_HTTP:
            si.wait_for_http()
            si.serialize(n)
        if uconf.WAIT_FOR_SSH:
            si.wait_for_ssh()
        if uconf.COPY_CODE:
            execute(_run_on_nodes, si.ip,
                    _make_download_script(code_url))
        if uconf.OPEN_IN_BROWSER:
            si.open_in_browser()
        if uconf.OPEN_SSH:
             si.open_ssh_term()
        if uconf.ADD_TO_ANSIBLE_HOSTS:
            si.add_to_ansible_hosts()

    if uconf.RUN_ANSIBLE:
        _run_ansible(conf, ["configuration"])

@click.group()
def config():
    """Manage launch configurations
    """
    _check_required_env_vars()
    pass

@click.group()
def launch():
    """Request and launch instances with a particular configuration
    """
    pass

@click.group()
def ansible():
    """Manage ansible playbooks for configurations
    """
    pass

launch.add_command(from_config)

config.add_command(ls)
config.add_command(new)
config.add_command(edit)

ansible.add_command(edit_ansible)


@click.group()
@click.argument("conf")
@click.argument("n")
@click.pass_context
def run(ctx, conf, n):
    instance = from_json(conf, n)
    ctx.obj['instance'] = instance
    ctx.obj['conf'] = conf
    pass

def ls(conf):
    with open("{}.pickle".format(conf), "rb") as f:
        instances = pickle.load(f)
    print(["{}: {}".format(n, instance.ip) for n, instance in enumerate(instances)])

@click.command()
@click.pass_context
def ssh(ctx):
    ctx.obj['instance'].open_ssh_term()

@click.command()
@click.pass_context
def browser(ctx):
    ctx.obj['instance'].open_in_browser()

@click.command()
@click.pass_context
def upload_code(ctx):
    instance = ctx.obj['instance']
    conf = ctx.obj['conf']
    uconf = paths._load_config(conf)
    code_url = upload_archive(os.getcwd(),
                              conf,
                              uconf.ARCHIVE_EXCLUDES,
                              uconf.S3_BUCKET,
                              skip_archive=False)
    env.key_filename = expanduser(uconf.PATH_TO_KEY)
    env.user = 'ubuntu'
#    env.hosts = [instance.ip]
    with settings(host_string=instance.ip):
        res = fabric.operations.run(_make_download_script(code_url))

@click.command()
@click.pass_context
def rsync(ctx):
    instance = ctx.obj['instance']
    conf = ctx.obj['conf']
    uconf = paths._load_config(conf)
    cmd = ["rsync", "-az",
           "-p",
           "-e",
           'ssh -i {}'.format(expanduser(uconf.PATH_TO_KEY)),
           ".",
           "{}@{}:/home/rstudio/research".format(
               uconf.SSH_USER_NAME,
               instance.ip)]
    _highlight("Prepping to sync entire code directory")

    get_total_size = (cmd[:1] + ["-vnaz"] + cmd[2:])
    ps = subprocess.Popen(get_total_size,
                          stdout=subprocess.PIPE)
    output = subprocess.check_output(('grep', 'total'),
                                     stdin=ps.stdout)
    ps.wait()
    _highlight(output.decode("utf-8").strip())

    if click.confirm('Do you want to continue?'):
        subprocess.call(cmd)

run.add_command(ansible)
run.add_command(ssh)
run.add_command(browser)
run.add_command(upload_code)
run.add_command(rsync)

@click.group()
@click.argument("conf")
@click.argument("n")
@click.pass_context
def data(ctx, conf, n):
    instance = from_json(conf, n)
    ctx.obj['instance'] = instance
    ctx.obj['conf'] = conf
    pass

@click.command()
@click.pass_context
def diff(ctx):
    instance = ctx.obj['instance']
    conf = ctx.obj['conf']
    uconf = paths._load_config(conf)
    cmd = ["rsync", "-navz",
           "-e",
           'ssh -i {}'.format(expanduser(uconf.PATH_TO_KEY)),
           "{}@{}:/home/rstudio/research/{}".format(
               uconf.SSH_USER_NAME,
               instance.ip,
               uconf.DATA_DIR),
           "{}".format(uconf.DATA_DIR)]
    #print(">> cmd: ", " ".join(cmd))
    _highlight("These files will be changed on a sync:")
    subprocess.call(cmd)

@click.command()
@click.pass_context
def sync(ctx):
    instance = ctx.obj['instance']
    conf = ctx.obj['conf']
    uconf = paths._load_config(conf)
    #rsync -avz -e "ssh -p1234  -i /home/username/.ssh/1234-identity" dir user@server:

    cmd = ["rsync", "-avz",
           "--info=progress2"
           "-e",
           'ssh -i {}'.format(expanduser(uconf.PATH_TO_KEY)),
           "{}@{}:/home/rstudio/research/{}".format(
               uconf.SSH_USER_NAME,
               instance.ip,
               uconf.DATA_DIR),
           "{}".format(uconf.DATA_DIR)]
    _highlight("Syncing files using rsync...")
    if click.confirm('Do you want to continue?'):
        subprocess.call(cmd)

data.add_command(diff)

@click.group()
def cli():
    pass

cli.add_command(launch)
cli.add_command(config)
cli.add_command(run)
cli.add_command(data)


if __name__ == "__main__":
    cli(obj={})
