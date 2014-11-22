import configparser
from os import getenv, makedirs
from os.path import abspath, dirname, exists, expanduser, join, realpath


class Config:
    """
    Responsible for getting configuration from specific path or communicate with
    user to init it with user or default values.
    Implements Borg pattern
    """
    __shared_state = {}

    def __init__(self, configpath=None):
        self.__dict__ = self.__shared_state
        self.config = configparser.ConfigParser()
        self.default_paths = {
            'log':   lambda: abspath(expanduser('~/.dnevnichok.log')),
            'notes': lambda: abspath(expanduser('~/notebook')),
            'db':    lambda: join(self.get_path('notes'), '.dnevnichok.db')
        }
        self.configpath = configpath if configpath else self.get_configpath()
        if not exists(self.configpath):
            self.initial_config()
        else:
            self.config.read(self.configpath)

    def get_path(self, path):
        return self.config.get('Path', path, fallback=self.default_paths[path]())

    def get_configpath(self):
        """ Try to get $XDG_CONFIG_HOME or fallback to ~/.config """
        if hasattr(self, 'configpath'):
            return self.configpath

        try:
            configpath = realpath(expanduser(getenv('XDG_CONFIG_HOME')))
        except AttributeError:
            configpath = realpath(expanduser('~/.config'))
        finally:
            configfile = join(configpath, 'dnevnichok', 'config')

        return configfile

    def initial_config(self):
        """ Ask user about configuration and create it """
        path = self.get_configpath()
        print("It seems that it your first run.\n"
              "I'm creating a configfile at {}.\n".format(path))
        makedirs(dirname(path), 0o755)
        self.config.add_section('Paths')

        default_notesdir = self.get_path('notes')
        notesdir = input("Specify dir, where you keep your notes.\n"
                         "(default is {}): ".format(default_notesdir))
        notesdir = notesdir if notesdir and not notesdir.isspace() else default_notesdir
        self.config['Paths']['notes'] = notesdir

        default_dbpath = self.get_path('db')
        dbpath = input("Specify path to cache db.\n"
                       "(default is inside your notes dir {}): ".format(default_dbpath))
        dbpath = dbpath if dbpath and not dbpath.isspace() else default_dbpath
        self.config['Paths']['db'] = dbpath

        default_logpath = self.get_path('log')
        logpath = input("Specify dir, where you would like to keep debug log.\n"
                        "(default is ~/.dnevnichok.log): ")
        logpath = logpath if logpath and not logpath.isspace() else default_logpath
        self.config['Paths']['log'] = logpath

        with open(self.configpath, 'w') as configfile:
            self.config.write(configfile)

    def get(self, section, option, fallback):
        """ Fallback method """
        return self.config(section, option, fallback=fallback)
