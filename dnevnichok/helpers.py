import configparser
from os import getenv, makedirs
from os.path import dirname, exists, expanduser, join, realpath


def init_config(configpath, notesdir=None):
    """
    Create config file and return ConfigParser object
    """
    if not notesdir or notesdir.isspace():
        notesdir = "~/notebook"
    config = configparser.RawConfigParser()
    config.add_section('Paths')
    config.set('Paths', 'notes', notesdir)
    config.set('Paths', 'db', join(notesdir, '.dnevnichok.db'))
    with open(configpath, 'w') as configfile:
        config.write(configfile)
    return config

def get_config_path():
    """
    Try to get $XDG_CONFIG_HOME or fallback to ~/.config
    """
    try:
        configpath = realpath(expanduser(getenv('XDG_CONFIG_HOME')))
    except AttributeError:
        configpath = realpath(expanduser('~/.config'))
    finally:
        configfile = join(configpath, 'dnevnichok', 'config')

    return configfile


def get_config(configfile=None):
    if not configfile:
        configfile = get_config_path()
    if not exists(configfile):
        print("It seems that it your first run.\n"
              "I'm creating a configfile at {}.\n".format(configfile))
        makedirs(dirname(configfile), 0o700)
        notesdir = input("Specify dir, where you will be keep your notes.\n"
                         "(default is ~/notebook): ")
        config = init_config(configfile, str(notesdir))
    else:
        config = configparser.RawConfigParser()
        config.read(configfile)
    return config
