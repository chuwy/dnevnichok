"""
Managers are responsible for providing items to pane.
Each created only once and assigned to application.
Application itself decides when to switch over managers.
"""

from collections import deque
import logging
import sqlite3

from dnevnichok.core import DirItem, NoteItem, TagItem

logging.basicConfig(filename='noter.log')


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
        self._bases = deque()
        self.root_path = root_path
        self.base = root_path
        self.chpath(root_path)
        self._conn = sqlite3.connect(dbpath)

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
            cur.execute("""SELECT dirs_path.descendant, n.title, n.size
                           FROM dirs
                           JOIN dirs_path     ON dirs_path.ancestor = dirs.id
                           JOIN dirs as n     ON dirs_path.descendant = n.id
                           WHERE dirs_path.direct = 1 and dirs_path.ancestor = {}""".format(str(self.base)))
            dirs = cur.fetchall()
            cur.execute("""SELECT n.id, n.title, n.size, n.full_path, n.pub_date, n.mod_date, n.real_title
                           FROM notes AS n
                           WHERE n.dir_id = {}""".format(self.base))
            notes = cur.fetchall()
            return [DirItem(t[0], title=t[1], path=t[1], size=t[2]) for t in dirs] + \
                   sorted([NoteItem(t[0], title=t[1], size=t[2], path=t[3], pub_date=t[4], mod_date=t[5], real_title=t[6]) for t in notes], key=lambda i: i.pub_date, reverse=True)



class TagManager(ManagerInterface):
    def __init__(self, dbpath):
        self._conn = sqlite3.connect(dbpath)
        self.base = None            # None means root
        self.last_tag = None

    def get_items(self):
        def get_size(tag_id):
            cur.execute("""SELECT COUNT(*)
                        FROM note_tags
                        WHERE tag_id = {}""".format(tag_id))
            return int(cur.fetchone()[0])

        with self._conn:
            cur = self._conn.cursor()
            if self.base is None:
                cur.execute("SELECT id, title FROM tags")
                rows = cur.fetchall()
                return sorted([TagItem(t[0], title=t[1], size=get_size(t[0])) for t in rows], key=lambda i: i.get_size(), reverse=True)
            # else
            cur.execute("""SELECT n.id, n.title, n.real_title, n.full_path, n.pub_date, n.mod_date, n.size FROM notes AS n
                           JOIN note_tags AS nt ON (nt.note_id = n.id)
                           JOIN tags as t ON (nt.tag_id = t.id)
                           WHERE t.id = {}""".format(self.base))
            rows = cur.fetchall()
            return sorted([NoteItem(t[0], title=t[1], real_title=t[2], path=t[3], pub_date=t[4], mod_date=t[5], size=t[6]) for t in rows], key=lambda i: i.pub_date, reverse=True)

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
        self.base = None

    def get_items(self):
        with self._conn:
            cur = self._conn.cursor()
            cur.execute("SELECT id, title, full_path, pub_date, mod_date, size, real_title FROM notes")
            rows = cur.fetchall()
            return sorted([NoteItem(t[0], title=t[1], path=t[2], pub_date=t[3], mod_date=t[4], size=t[5], real_title=t[6]) for t in rows], key=lambda i: i.pub_date, reverse=True)

    def root(self): pass

    def parent(self): pass

    def chpath(self, tag): pass
