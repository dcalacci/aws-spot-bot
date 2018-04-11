import os
import click
import glob
import json
import subprocess

from os.path import expanduser

from .. import configs

def _custom_path():
    home = expanduser("~")
    return "{}/.lab_config".format(home)

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
    return [s.split(".py")[0] for s in os.listdir(_custom_path()) if '.py' in s]

def _get_config_names():
    import pkgutil
    return [m for i,m,p in pkgutil.iter_modules(configs.__path__)]

def _all_config_names():
    return _get_config_names() + _get_custom_config_names()

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

def _find_inventory(name):
    return os.path.join(_custom_path(), "ansible", "{}_hosts".format(name))

def _load_module_from_path(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(path)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)

def _load_config(name):
    import sys
    sys.path.append(_custom_path())
    path = _find_config(name)
    return __import__(name)
