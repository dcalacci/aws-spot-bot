import os
import click
from os.path import expanduser


def _check_required_env_vars():
    keys = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "KEY_NAME"]
    in_env = [k in os.environ for k in keys]
    assert all(in_env), 'Please set the environment variables "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"!'
    return True

if _check_required_env_vars():
    from .configs import default as uconf

    from . import configs
    from .utils import pricing_util
    from .utils.aws_spot_instance import AWSSpotInstance
    from .utils.aws_spot_exception import SpotConstraintException

@click.command()
@click.argument("qty", required=True)
def launch_instances(qty):
    """Launches QTY instances and returns the instance objects."""
    best_az = pricing_util.get_best_az()
    launched_instances = []
    print("Best availability zone:", best_az.name)

    for idx in range(qty):
        print('>> Launching instance #{}'.format(idx))
        si = AWSSpotInstance(best_az.region, best_az.name, uconf.INSTANCE_TYPES[0], uconf.AMI_ID, uconf.BID)
        si.request_instance()
        try:
            si.get_ip()
        except SpotConstraintException as e:
            print(">> ", e.message)
            si.cancel_spot_request()
            continue
        launched_instances.append(si)

    return launched_instances

def _custom_path():
    home = expanduser("~")
    return "{}/.lab_configs".format(home)

def _has_custom_configs():
    return len(os.listdir(_custom_path())) > 0

def _print_names(names):
    for name in names:
        print("- {}".format(name))

def _has_custom_configs():
    return os.path.exists(_custom_path())

def _get_custom_config_names():
    if not _has_custom_configs():
        return []
    return [s.split(".py")[0] for s in os.listdir(_custom_path())]


def _get_config_names():
    import pkgutil
    return [m for i,m,p in pkgutil.iter_modules(configs.__path__)]

def _print_all_configurations():
    custom_names = _get_custom_config_names()
    names = _get_config_names()
    print("Available default configurations:\n")
    _print_names(names)
    print("Available custom configurations:\n")
    _print_names(custom_names)

def _find_config(name):
    """Returns full path for configuration file with the given name.
    """
    if name in _get_config_names():
        return os.path.join(configs.__path__[0], "{}.py".format(name))
    elif name in _get_custom_config_names():
        return os.path.join(_custom_path(), "{}.py".format(name))
    else:
        return None

@click.command()
@click.argument("uconf", type=click.Path(), required=True)
def from_config(uconf):
    """Launches a number of instances with the given configuration file.

    """

    instances = launch_instances(uconf.QTY_INSTANCES)

    for si in instances:
        if uconf.WAIT_FOR_HTTP:
            si.wait_for_http()
        if uconf.WAIT_FOR_SSH:
            si.wait_for_ssh()
        if uconf.OPEN_IN_BROWSER:
            si.open_in_browser()
        if uconf.OPEN_SSH:
             si.open_ssh_term()
        if uconf.ADD_TO_ANSIBLE_HOSTS:
            si.add_to_ansible_hosts()

    if uconf.RUN_ANSIBLE:
        os.system('cd ansible && ansible-playbook -s play.yml')


@click.command()
@click.argument("mname", required=False, default=None)
def ls(mname):
    """List available configs.

    If a configuration name is provided (MNAME), it will print the contents of
    that configuration file.

    """
    if not mname:
        _print_all_configurations()
    else:
        if mname in _get_config_names():
            with open(os.path.join(configs.__path__[0], "{}.py".format(mname)), 'r') as fin:
                print(fin.read())
        elif mname in _get_custom_config_names():
            with open(os.path.join(_custom_path(), "{}.py".format(mname)), 'r') as fin:
                print(fin.read())
        else:
            print("No configuration with that name. Available configurations are:")
            _print_all_configurations()


@click.command()
@click.argument("name", required=True)
@click.option("--from_existing", type=click.Path(),
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
    file_to_copy = _find_config(from_existing)
    shutil.copyfile(file_to_copy,
                    "{}/.lab_configs/{}.py".format(home, name))

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

launch.add_command(launch_instances)
launch.add_command(from_config)

config.add_command(ls)
config.add_command(new)


@click.group()
def cli():
    pass

cli.add_command(launch)
cli.add_command(config)

if __name__ == "__main__":
    cli()
