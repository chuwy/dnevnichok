"""
Managers are responsible for providing items to pane.
Each created only once and assigned to application.
Application itself decides when to switch over managers.
"""

from collections import deque
import logging
import sqlite3

from dnevnichok.core import DirItem, NoteItem, TagItem


logger = logging.getLogger(__name__)


class ManagerInterface:
    def chpath(self, path):
        """
        Return none. Just changes current state
        """
        raise NotImplemented
    def get_items(self): raise NotImplemented
    def parent(self):
        """
        Return None if we can't go parent or directory from where we moving out
        """
        raise NotImplemented


class FileManager(ManagerInterface):
    def __init__(self, root_path, dbpath):
        self._conn = sqlite3.connect(dbpath)
        self._conn.row_factory = sqlite3.Row
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
                   sorted([NoteItem(note[0], note) for note in notes], key=lambda i: i.pub_date, reverse=True)


class TagManager(ManagerInterface):
    def __init__(self, dbpath):
        self._conn = sqlite3.connect(dbpath)
        self._conn.row_factory = sqlite3.Row
        self.base = None            # None means root
        self.last_tag = None

    def get_items(self):
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
                rows = cur.fetchall()
                return sorted([NoteItem(row[0], row) for row in rows], key=lambda i: i.pub_date, reverse=True)

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
    def __init__(self, dbpath):
        self._conn = sqlite3.connect(dbpath)
        self._conn.row_factory = sqlite3.Row
        self.base = None

    def get_items(self):
        with self._conn:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM notes")
            rows = cur.fetchall()
            return sorted([NoteItem(row[0], row) for row in rows], key=lambda i: i.pub_date, reverse=True)

    def root(self): pass

    def parent(self): pass

    def chpath(self, path): pass


class FavoritesManager(ManagerInterface):
    def __init__(self, dbpath):
        self._conn = sqlite3.connect(dbpath)
        self._conn.row_factory = sqlite3.Row
        self.base = None

    def get_items(self):
        with self._conn:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM notes WHERE favorite=1")
            rows = cur.fetchall()
            return sorted([NoteItem(row[0], row) for row in rows], key=lambda i: i.pub_date, reverse=True)

    def root(self): pass

    def parent(self): pass

    def chpath(self, path): pass
