import os
import sys
import sqlite3
import inspect
import logging

from dnevnichok.aux import EventQueue
from dnevnichok.helpers import get_config


config = get_config()
dbpath = os.path.abspath(os.path.expanduser(config.get('Paths', 'db')))


class Command:
    def ensure(self):
        return True     # Most commands do not need confirmation

    def fill_args(self):
        self.item = self.executor.get_current_item()


class deleteCommand(Command):
    def __init__(self, executor, args):
        self.executor = executor
        self.conn = sqlite3.connect(dbpath)

        self.item = None

    def ensure(self):
        return self.executor.ensure('Are you sure you want to delete {}? [y/N]  '.format(self.item.get_path()))

    def run(self):
        exit_code = os.system('rm ' + self.item.get_path())
       # exit_code = 0
       # EventQueue.push(('reload',))
        if exit_code == 0:
            with self.conn:
                cur = self.conn.cursor()
                cur.execute('DELETE FROM notes WHERE id = {}'.format(self.item.id))
                EventQueue.push(('reload',))


def get_all_commands():
    commands = {}
    for name, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(obj):
            if len(name) > 7 and name.endswith('Command'):
                commands.update({name[:-7]: obj})
    return commands

