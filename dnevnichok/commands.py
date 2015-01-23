import curses
import os
import sys
import sqlite3
import inspect
import logging

from dnevnichok.config import Config
from dnevnichok.core import NoteItem, TagItem
from dnevnichok.events import event_hub
from dnevnichok.populate import parse_note


config = Config()
dbpath = config.get_path('db')
logger = logging.getLogger(__name__)


class InsufficientArguments(Exception):
    def __init__(self, args):
        self.message = str(args) + " arg required"


class Command:
    def __init__(self, executor, args: tuple):
        pass

    def ensure(self):
        return True     # Most commands do not need confirmation

    def input_args(self):
        pass


class quitCommand(Command):
    def __init__(self, executor, args):
        self.executor = executor

    def run(self):
        event_hub.trigger(('exit',))


class updateCommand(Command):
    def __init__(self, executor, args):
        self.executor = executor

    def run(self):
        os.system('git pull')
        os.system('git push --porcelain')
        event_hub.trigger(('reload',))


class deleteCommand(Command):
    def __init__(self, executor, args):
        self.executor = executor
        self.conn = sqlite3.connect(dbpath)

        self.item = self.executor.app.window.get_current_item()

    def ensure(self):
        return self.executor.ensure('Are you sure you want to delete {}? [y/N]  '.format(self.item.get_path()))

    def run(self):
        table = None
        if isinstance(self.item, NoteItem):
            exit_code = os.system('rm ' + self.item.get_path())
            if exit_code == 0:
                table = 'notes'
        elif isinstance(self.item, TagItem):
            table = 'tags'

        if table:
            with self.conn:
                cur = self.conn.cursor()
                cur.execute('DELETE FROM {} WHERE id = {}'.format(table, self.item.id))
            event_hub.trigger(('reload',))
            curses.curs_set(1)  # THIS is sought-for hack
            curses.curs_set(0)


class commitCommand(Command):
    def __init__(self, executor, args: tuple):
        self.executor = executor

    def run(self):
        os.system('git add .')
        os.system('git commit')
        event_hub.trigger(('reload',))
        curses.curs_set(1)  # THIS is sought-for hack
        curses.curs_set(0)


class newCommand(Command):
    def __init__(self, executor, args: tuple):
        self.executor = executor
        self.conn = sqlite3.connect(dbpath)
        self.path = None
        self.content = ''

        args_num = len(args)
        if args_num == 0:
            raise InsufficientArguments(1)
        if args_num > 0:
            self.item_title = args[0] if args[0].endswith('.rst') else args[0] + '.rst'
        if args_num > 1:
            self.path = args[1]
            self.content = ':tags: diary'

    def run(self):
        base_path = self.executor.app.manager_hub.get_current_dir() if not self.path else self.path
        dir_id = self.executor.app.manager_hub.get_path_id(base_path)
        note_path = os.path.join('.', base_path, self.item_title)
        if os.path.exists(note_path):
            event_hub.trigger(('print', 'File {} already exists'.format(note_path)))
            return
        os.system('touch {}'.format(note_path))
        os.system('echo "{}" >> {}'.format(self.content, note_path))
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

            event_hub.trigger(('reload',))
            curses.curs_set(1)  # THIS is sought-for hack
            curses.curs_set(0)


def get_all_commands() -> dict:
    """
    Returns all classes from this module which ends with `Command`
    """
    commands = {}
    for name, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(obj):
            if len(name) > 7 and name.endswith('Command'):
                commands.update({name[:-7]: obj})
    return commands


class Executor:
    """
    Responsible for take find all available commands, pick right one and
    give it everything it needs. Also stores history.
    """
    def __init__(self, app):
        self.app = app
        self.commands = get_all_commands()

    def run_command(self, command: str):
        command, *args = command.split()
        try:
            CommandClass = self.commands[command]
        except KeyError:
            event_hub.trigger(('print', "Unknown command: " + command))
            return

        try:
            execution = CommandClass(self, args)
        except InsufficientArguments as e:
            event_hub.trigger(('print', e.message))
            return

        proceed = execution.ensure()
        if proceed:
            execution.run()

    def ensure(self, text, tries=0):
        choice = self.app.window.input(text)
        if choice in 'yY':
            return True
        elif choice in 'nN':
            return False
        elif tries > 3:
            event_hub.trigger(('print', "Ok. Just have a good day"))
            return False
        else:
            return self.ensure(text, tries+1)

    def get_current_item(self):
        return self.app.window.get_current_item()


