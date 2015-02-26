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
from dnevnichok.core import DirItem, MonthItem, NoteItem, TagItem
from dnevnichok.config import config
from dnevnichok.events import event_hub
from dnevnichok.populate import repopulate_db

logger = logging.getLogger(__name__)
dbpath = config.get_path('db')
backend = GitCommandBackend()
backend.update_statuses()


def add_git_status(row: sqlite3.Row):
    """ Helper function for NoteItems """
    item_dict = dict(row)
    if 'full_path' in item_dict:
        path = item_dict['full_path'][2:]
        stat = backend.notes_status.get(path, '')
        item_dict.update({'status': stat})
    return item_dict


class EmptyManagerException(Exception):
    pass


class ManagerInterface:
    _conn = sqlite3.connect(dbpath)
    _conn.row_factory = sqlite3.Row
    _notes = []
    base = None     # where we now

    def chpath(self, path):
        """Return none. Just changes current state"""
        pass

    def fetch_items(self) -> None:
        """Fetch items from DB and store internally"""
        pass

    def parent(self):
        """Return None if we can't go parent or directory from where we moving out"""
        pass

    def process_parent(self):
        last_active = self.parent()
        if not last_active:
            return
        if isinstance(self, CategoryManagerInterface):
            item = self.category_class(last_active)
        else:
            item = DirItem(last_active)
        items = self.get_items()
        last_active_index = items.index(item)
        event_hub.trigger(('show', items, last_active_index))

    def process_root(self):
        """Called on initialization of every manager """
        items = self.get_items()
        event_hub.trigger(('show', items))

    def process_open(self, item):
        active = None
        if isinstance(item, NoteItem):
            subprocess.call(["vim", item.get_path()])
            active = item
            curses.curs_set(1)  # THIS is sought-for hack
            curses.curs_set(0)
        else:
            self.chpath(item.id)

        items = self.get_items()
        last_active_index = items.index(active) if active and active in items else 0
        event_hub.trigger(('show', items, last_active_index))

    def get_tags(self, id: int):
        with self._conn:
            cur = self._conn.cursor()
            cur.execute("""SELECT t.title
                           FROM tags AS t
                           JOIN note_tags AS nt ON (t.id = nt.tag_id)
                           JOIN notes AS n ON (n.id = nt.note_id)
                           WHERE n.id = {}""".format(id))
            tags = sorted([tag['title'] for tag in cur.fetchall()])
            return tags

    def get_items(self) -> list:
        """Return list of dnevnichok.core.Items
        If you wish to overload get_items() don't forget to invoke fetch_items"""
        backend.update_statuses()
        self.fetch_items()

        return sorted([NoteItem(row[0], add_git_status(row), tags=self.get_tags(row[0])) for row in self._notes],
                      key=lambda i: i.pub_date if i.pub_date else 'Z',
                      reverse=True)


class OneSelectManagerInterface(ManagerInterface):
    """ Subclasses need only to set sql statement to select necessary notes
    and hotkey to invoke a manger
    """
    sql = None
    sql_args = None

    def __init__(self):
        if not self.sql:
            raise NotImplemented("User class should give a SQL SELECT statement")

    def fetch_items(self):
        with self._conn:
            cur = self._conn.cursor()
            if hasattr(self, 'update_sql'):
                self.update_sql()
                cur.execute(self.get_sql(), self.sql_args)
            else:
                cur.execute(self.get_sql())
            self._notes = cur.fetchall()
            if not self._notes:
                raise EmptyManagerException

    def get_sql(self) -> str:
        return self.sql


class CategoryManagerInterface(OneSelectManagerInterface):
    categories = []
    previous_category = None
    category_sql = None
    category_class = None

    def __init__(self):
        self.base = None                # current category
        self.previous_category = None

    def get_category_sql(self) -> str:
        return self.category_sql

    def fetch_items(self):
        with self._conn:
            cur = self._conn.cursor()
            if self.base is None:
                cur.execute(self.get_category_sql())
                self.categories = cur.fetchall()
            else:
                cur.execute(self.get_sql().format(self.base))
                self._notes = cur.fetchall()

    def root(self):
        self.chpath(None)

    def parent(self):
        if self.base is None:    # we're already in the root
            return
        self.chpath(None)
        return self.previous_category

    def chpath(self, goto_category):
        self.previous_category = self.base
        self.base = goto_category

    def get_items(self) -> list:
        """Return list of dnevnichok.core.Items
        If you wish to overload get_items() don't forget to invoke fetch_items"""
        backend.update_statuses()
        self.fetch_items()

        if self.base is None:
            return sorted([self.category_class(category[0], category) for category in self.categories],
                          key=lambda i: i.get_path(),
                          reverse=True)
        else:
            return super().get_items()


class AllManager(OneSelectManagerInterface):
    key = 'a'
    sql = "SELECT * FROM notes"


class FavoritesManager(OneSelectManagerInterface):
    key = 'F'
    sql = "SELECT * FROM notes WHERE favorite=1"


class ModifiedManager(OneSelectManagerInterface):
    key = 'M'
    sql = "SELECT * FROM notes WHERE full_path IN ({})"
    sql_args = []

    def update_sql(self):
        self.sql_args  = ['./' + path for path in backend.notes_status.keys()]
        placeholders = ', '.join('?' for _ in self.sql_args)
        self.sql = ModifiedManager.sql.format(placeholders)


class FileManager(ManagerInterface):
    key = 'f'

    def __init__(self):
        self._dirs = []
        self._bases = deque()
        self.root_path = 1
        self.base = self.root_path
        self.chpath(self.root_path)

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
        self.fetch_items()
        return [DirItem(dir[0], dir) for dir in self._dirs] + super().get_items()

    def fetch_items(self):
        with self._conn:
            cur = self._conn.cursor()
            cur.execute("""SELECT d.*
                           FROM dirs_path AS dp
                           LEFT JOIN dirs AS d ON dp.descendant = d.id
                           WHERE dp.direct = 1 and dp.ancestor = {}""".format(str(self.base)))
            self._dirs = cur.fetchall()
            cur.execute("""SELECT *
                           FROM notes
                           WHERE dir_id = {}""".format(self.base))
            self._notes = cur.fetchall()


class MonthManager(CategoryManagerInterface):
   key = 'm'
   sql = """SELECT n.*
            FROM notes AS n
            WHERE n.pub_date LIKE '{}' || '%'"""
   category_sql = """SELECT d.months AS title, count(d.months) AS size
                     FROM notes AS n
                     JOIN (SELECT DISTINCT strftime('%Y-%m', substr(n.pub_date, 1, 20)) AS months
                           FROM notes AS n) AS d
                     ON n.pub_date LIKE d.months || '%'
                     GROUP BY d.months"""
   category_class = MonthItem


class TagManager(CategoryManagerInterface):
    key = 't'
    sql = """SELECT n.*
             FROM notes AS n
             JOIN note_tags AS nt ON (nt.note_id = n.id)
             JOIN tags as t ON (nt.tag_id = t.id)
             WHERE t.id = {}"""
    category_sql = """SELECT t.id, t.title, COUNT(t.title) AS size
                      FROM tags AS t
                      JOIN note_tags AS nt
                      ON (t.id = nt.tag_id)
                      GROUP BY t.title"""
    category_class = TagItem


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
        self._previous = self._active
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
            try:
                self.active.process_root()
            except EmptyManagerException:
                self.switch_by_name(self._previous)
                event_hub.trigger(('print', 'Empty manager'))
        else:
            logger.error("Unexisting manager: {}".format(str(name)))

    def get_current_dir(self) -> str:
        """
        Return current dir (may be should based on current item path?)
        """
        return self.manager_names['file'].get_current_path()

    def get_path_id(self, path: str):
        return self.manager_names['file'].get_path_id(path)

    def get_items(self) -> list:
        try:
            items = self.active.get_items()
        except sqlite3.OperationalError:
            logger.info("It seems DB didn't existed. Try to repopulate.")
            print("It seems DB didn't existed. Populating... It may take some time.")
            repopulate_db()
            items = self.active.get_items()
        except EmptyManagerException:
            self.switch_by_name(self._previous)
            items = self.active.get_items()
        return items
