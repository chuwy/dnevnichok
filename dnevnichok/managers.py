"""
Managers are responsible for providing items to pane.
Each created only once and assigned to application.
Application itself decides when to switch over managers.
"""

from collections import deque
import curses
import inspect
import logging
import sqlite3
import subprocess
import sys

from dnevnichok.backend import GitCommandBackend
from dnevnichok.core import DirItem, NoteItem, TagItem
from dnevnichok.config import config
from dnevnichok.events import event_hub
from dnevnichok.populate import repopulate_db

logger = logging.getLogger(__name__)
dbpath = config.get_path('db')
backend = GitCommandBackend()
backend.update_statuses()


def add_status(row):
    """ Helper function for NoteItems """
    item_dict = dict(row)
    if 'full_path' in item_dict:
        path = item_dict['full_path'][2:]
        stat = backend.notes_status.get(path, '')
        item_dict.update({'status': stat})
    return item_dict


class ManagerInterface:
    _conn = sqlite3.connect(dbpath)
    _conn.row_factory = sqlite3.Row
    base = None     # where we now

    def chpath(self, path):
        """
        Return none. Just changes current state
        """
        raise NotImplemented
    def get_items(self) -> list:
        """
        Return list of dnevnichok.core.Items
        """
        raise NotImplemented

    def parent(self):
        """
        Return None if we can't go parent or directory from where we moving out
        """
        raise NotImplemented

    def process_parent(self):
        last_active = self.parent()
        if not last_active:
            return
        item = TagItem(last_active) if isinstance(self, TagManager) else DirItem(last_active)
        items = self.get_items()
        last_active_index = items.index(item)
        event_hub.trigger(('show', items, last_active_index))

    def process_root(self):
        items = self.get_items()
        event_hub.trigger(('show', items))

    def process_open(self, item):
        active = None
        if isinstance(item, (DirItem, TagItem,)):
            self.chpath(item.id)
        elif isinstance(item, NoteItem):
            subprocess.call(["vi", item.get_path()])
            active = item
            curses.curs_set(1)  # THIS is sought-for hack
            curses.curs_set(0)

        items = self.get_items()
        last_active_index = items.index(active) if active else 0
        event_hub.trigger(('show', items, last_active_index))


class FileManager(ManagerInterface):
    key = 'f'

    def __init__(self):
        root_path = 1
        self._bases = deque()
        self.root_path = root_path
        self.base = root_path
        self.chpath(root_path)

    def get_current_path(self):
        with self._conn:
            cur = self._conn.cursor()
            cur.execute("""SELECT d.title
                           FROM dirs_path AS dp
                           JOIN dirs as d
                           ON dp.ancestor == d.id
                           WHERE descendant = {}
                           ORDER BY d.id ASC""".format(str(self.base)))
            parents = map(lambda p: p[0], cur.fetchall())
            path = '/'.join(parents)
            return path

    def get_path_id(self, path: str):
        path = [p for p in path.split('/') if len(p) > 0 and p != '.']
        if len(path) == 1:
            with self._conn:
                cur = self._conn.cursor()
                cur.execute("""SELECT id FROM dirs WHERE title = '{}'""".format(path[0]))
                id = cur.fetchone()['id']
            return id
        else:
            with self._conn:
                logger.error("Implement path find ({})".format(str(path)))
                cur = self._conn.cursor()
                cur.execute("""SELECT id FROM dirs WHERE title = '{}'""".format(path))
                id = cur.fetchone()['id']
            return id


    def root(self):
        self.chpath(self.root_path)

    def parent(self):
        if self.base == self.root_path:
            return
        else:
            with self._conn:
                cur = self._conn.cursor()
                cur.execute("""SELECT dirs_path.ancestor
                               FROM dirs_path
                               WHERE dirs_path.descendant == {}
                               AND direct = 1""".format(str(self.base)))
                parent = cur.fetchone()[0]
                self.chpath(parent)
                return self._bases.pop()

    def chpath(self, path):
        self._bases.append(self.base)
        self.base = path

    def get_items(self):
        backend.update_statuses()
        with self._conn:
            cur = self._conn.cursor()
            cur.execute("""SELECT d.*
                           FROM dirs_path AS dp
                           LEFT JOIN dirs AS d ON dp.descendant = d.id
                           WHERE dp.direct = 1 and dp.ancestor = {}""".format(str(self.base)))
            dirs = cur.fetchall()
            cur.execute("""SELECT *
                           FROM notes
                           WHERE dir_id = {}""".format(self.base))
            notes = cur.fetchall()
            return [DirItem(dir[0], dir) for dir in dirs] + \
                   sorted([NoteItem(note[0], add_status(note)) for note in notes], key=lambda i: i.pub_date if i.pub_date else 'Z', reverse=True)


class TagManager(ManagerInterface):
    key = 't'

    def __init__(self):
        self.last_tag = None

    def get_items(self):
        backend.update_statuses()
        with self._conn:
            cur = self._conn.cursor()
            if self.base is None:
                cur.execute("""SELECT t.id, t.title, COUNT(t.title) AS size
                               FROM tags AS t
                               JOIN note_tags AS nt
                               ON (t.id = nt.tag_id)
                               GROUP BY t.title""")
                rows = cur.fetchall()
                return sorted([TagItem(tag[0], tag) for tag in rows], key=lambda i: i.get_size(), reverse=True)
            else:
                cur.execute("""SELECT n.*
                               FROM notes AS n
                               JOIN note_tags AS nt ON (nt.note_id = n.id)
                               JOIN tags as t ON (nt.tag_id = t.id)
                               WHERE t.id = {}""".format(self.base))
                notes = cur.fetchall()
                return sorted([NoteItem(note[0], add_status(note)) for note in notes], key=lambda i: i.pub_date if i.pub_date else 'Z', reverse=True)

    def root(self):
        self.chpath(None)

    def parent(self):
        if self.base is None:    # we're already in the root
            return
        self.chpath(None)
        last, self.last_tag = self.last_tag, None
        return last

    def chpath(self, tag):
        self.last_tag = self.base
        self.base = tag


class AllManager(ManagerInterface):
    key = 'a'

    def get_items(self):
        backend.update_statuses()
        with self._conn:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM notes")
            rows = cur.fetchall()
            return sorted([NoteItem(row[0], add_status(row)) for row in rows], key=lambda i: i.mod_date if i.mod_date else 'Z', reverse=True)

    def root(self): pass

    def parent(self): pass

    def chpath(self, path): pass


class FavoritesManager(ManagerInterface):
    key = 'F'

    def get_items(self):
        with self._conn:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM notes WHERE favorite=1")
            rows = cur.fetchall()
            return sorted([NoteItem(row[0], add_status(row)) for row in rows], key=lambda i: i.pub_date if i.pub_date else 'Z', reverse=True)

    def root(self): pass

    def parent(self): pass

    def chpath(self, path): pass


class ManagerHub:
    """
    Responsible for switch active managers, load third-party managers
    """
    def __init__(self):
        self.manager_names = {} # {'tag': tag_manager}
        self.manager_keys = {}  # {'t': 'tag'}
        self.managers = self._get_builtin_managers() # {'tag': TagManager}

        for name, klass in self.managers.items():
            if klass.key in self.manager_keys:
                logger.warning("Key {} was already assigned to {}".format(klass.key, str(self.manager_keys[klass.key])))
            self.manager_names[name] = klass()
            self.manager_keys[klass.key] = name
        self._active = self.get_default_active()

        event_hub.register('root', lambda: self.active.process_root)
        event_hub.register('open', lambda e: self.active.process_open(e))
        event_hub.register('parent', lambda: self.active.process_parent())
        event_hub.register('reload', lambda: self.reload())

    def reload(self):
        items = self.get_items()
        event_hub.trigger(('show', items))

    @property
    def active(self) -> ManagerInterface:
        return self.manager_names[self._active]

    def _get_builtin_managers(self) -> dict:
        managers = {}
        for name, obj in inspect.getmembers(sys.modules[__name__]):
            if inspect.isclass(obj):
                if len(name) > 7 and name.endswith('Manager'):
                    managers.update({name[:-7].lower(): obj})
        return managers

    def _set_active(self, name: str):
        self._active = name

    def get_default_active(self) -> str:
        return 'all' if 'all' in self.manager_names else self.manager_names.keys()[0]

    def tied_to_manager(self, key: str) -> bool:
        return key in self.manager_keys.keys()

    def switch_by_key(self, key: str):
        try:
            name = self.manager_keys[key]
        except KeyError:
            logger.debug("Tried to switch manager with {} key".format(str(key)))
        else:
            self.switch_by_name(name)

    def switch_by_name(self, name: str):
        if name in self.manager_names:
            self._set_active(name)
            self.active.process_root()
        else:
            logger.error("Unexisting manager: {}".format(str(name)))

    def get_current_dir(self) -> str:
        """
        Return current dir (may be should based on current item path?)
        """
        return self.manager_names['file'].get_current_path()

    def get_path_id(self, path: str):
        return self.manager_names['file'].get_path_id(path)

    def get_items(self):
        try:
            items = self.active.get_items()
        except sqlite3.OperationalError:
            logger.info("It seems DB didn't existed. Try to repopulate.")
            print("It seems DB didn't existed. Populating... It may take some time.")
            repopulate_db()
            items = self.active.get_items()
        return items

