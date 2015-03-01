import curses
import os
import sys
import sqlite3
import subprocess
import inspect
import logging

from dnevnichok.backend import GitCommandBackend
from dnevnichok.config import Config
from dnevnichok.core import NoteItem, TagItem
from dnevnichok.events import event_hub
from dnevnichok.populate import parse_note


config = Config()
git = GitCommandBackend()
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

    def ensure(self):
        if git.repo_status:
            return self.executor.ensure("You have some uncommited changed. "
                                        "Do you really want to exit? [Y/n] ",
                                        default=True)
        else:
            return True

    def run(self):
        event_hub.trigger(('exit',))


class updateCommand(Command):
    def __init__(self, executor, args):
        self.executor = executor

    def run(self):
        commands = [['git', 'pull'], ['git', 'push', '--porcelain']]
        pull_status = 'Pull: Updated. '
        push_status = 'Push: Updated. '
        for command in commands:
            popen = subprocess.Popen(command,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
            while True:
                line = popen.stdout.readline().decode()
                if line.find('Already up-to-date') > -1:
                    pull_status = 'Pull: Already up-to-date. '
                if line.find('up to date') > -1:
                    push_status = 'Push: Already up-to-date. '
                if not line:
                    break
                logger.info(command[1] + ': ' + line)

        event_hub.trigger(('reload',))
        event_hub.trigger(('print', pull_status + push_status))


class deleteCommand(Command):
    def __init__(self, executor, args):
        self.executor = executor
        self.conn = sqlite3.connect(dbpath)
        self.item = self.executor.app.window.get_current_item()

    def ensure(self):
        return self.executor.ensure('Are you sure you want to delete {}? [y/N] '.format(self.item.get_path()),
                                    default=False)

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
        exit_code = os.system('vim ' + note_path)
        if exit_code == 0:
            git.add(note_path)
            note = parse_note(note_path, dir_id)
            with self.conn:
                cur = self.conn.cursor()
                cur.execute("""INSERT INTO notes(title, real_title, full_path, pub_date, mod_date, size, dir_id, favorite)
                               VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
                            (note.get_title(), note.real_title, note.path, note.pub_date, note.mod_date, note.get_size(), note.dir_id, note.favorite))
                note.id = cur.lastrowid
                for tag in note.tags:
                    cur.execute("INSERT OR IGNORE INTO tags(title) VALUES(?)", (tag,))
                    cur.execute("INSERT INTO note_tags(note_id, tag_id) VALUES(?, ?)", (note.id, cur.lastrowid,))

        event_hub.trigger(('reload',))
        curses.curs_set(1)  # THIS is sought-for hack
        curses.curs_set(0)


def get_all_commands() -> dict:
    """Returns all classes from this module which ends with `Command`"""
    commands = {}
    for name, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(obj):
            if len(name) > 7 and name.endswith('Command'):
                commands.update({name[:-7]: obj})
    return commands


class Executor:
    """Responsible for take find all available commands, pick right one and
    give it everything it needs. Also stores history.
    """
    def __init__(self, app):
        self.app = app
        self.commands = get_all_commands()

    def run_command(self, command: str):
        try:
            command, *args = command.split()
            CommandClass = self.commands[command]
        except KeyError:
            event_hub.trigger(('print', "Unknown command: " + command))
            return
        except ValueError:  # No command at all
            return

        try:
            execution = CommandClass(self, args)
        except InsufficientArguments as e:
            event_hub.trigger(('print', e.message))
            return

        proceed = execution.ensure()
        if proceed:
            execution.run()

    def ensure(self, text, default=True):
        choice = self.app.window.input(text).lower()
        if choice == 'y':
            return True
        elif choice == 'n':
            return False
        elif not choice:
            return default
        else:
            event_hub.trigger(('print', "Just yes or no"))
            return False

    def get_current_item(self):
        return self.app.window.get_current_item()
