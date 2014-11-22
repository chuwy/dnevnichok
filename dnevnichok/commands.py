import os
import sys
import sqlite3
import inspect
import logging

from dnevnichok.aux import EventQueue
from dnevnichok.config import Config
from dnevnichok.populate import parse_note


config = Config()
dbpath = config.get_path('db')


class InsufficientArguments(Exception):
    def __init__(self, args):
        self.message = str(args) + " arg required"


class Command:
    def ensure(self):
        return True     # Most commands do not need confirmation

    def input_args(self):
        pass

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
        if exit_code == 0:
            with self.conn:
                cur = self.conn.cursor()
                cur.execute('DELETE FROM notes WHERE id = {}'.format(self.item.id))
                EventQueue.push(('reload',))


class newCommand(Command):
    def __init__(self, executor, args):
        self.executor = executor
        self.conn = sqlite3.connect(dbpath)

        try:
            self.item_title = args[0]
        except IndexError:
            raise InsufficientArguments(1)

    def fill_args(self):
        self.executor.app.file_manager

    def run(self):
        dir_id = self.executor.app.file_manager.base
        base_path = self.executor.app.file_manager.get_current_path()
        note_path = os.path.join(base_path, self.item_title)
        os.system('touch ' + note_path)
        exit_code = os.system('vi ' + note_path)
        if exit_code == 0:
            note = parse_note(note_path, dir_id)
            with self.conn:
                cur = self.conn.cursor()
                cur.execute("""INSERT INTO notes(title, real_title, full_path, pub_date, mod_date, size, dir_id)
                            VALUES(?, ?, ?, ?, ?, ?, ?)""",
                            (note.get_title(), note.real_title, note.path, note.pub_date, note.mod_date, note.get_size(), note.dir_id))
                note.id = cur.lastrowid
                for tag in note.tags:
                    cur.execute("INSERT OR IGNORE INTO tags(title) VALUES(?)", (tag,))
                    cur.execute("INSERT INTO note_tags(note_id, tag_id) VALUES(?, ?)", (note.id, cur.lastrowid,))
                EventQueue.push(('reload',))


def get_all_commands():
    commands = {}
    for name, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(obj):
            if len(name) > 7 and name.endswith('Command'):
                commands.update({name[:-7]: obj})
    return commands
