"""
Managers are responsible for providing items to pane.
Each created only once and assigned to application.
Application itself decides when to switch over managers.
"""

from collections import deque
import logging
import os
import sqlite3


class ManagerInterface:
    def chpath(self, path): raise NotImplemented
    def get_items(self): raise NotImplemented
    def parent(self):
        """ Must return None if we can't go parent"""
        raise NotImplemented


class FileManager:
    def __init__(self, root_path):
        self.paths = deque()
        self.root_path = root_path
        self.curpath = root_path
        self.chpath(root_path)

    def root(self):
        self.chpath(self.root_path)

    def parent(self):
        if self.curpath == self.root_path:
            return
        else:
            self.chpath(os.path.abspath(os.path.join(self.curpath, '..')))
            return os.path.basename(self.paths.pop())

    def chpath(self, path):
        if path == '..':
            raise Exception("Call parent()")
        else:
            self.paths.append(self.curpath)
            self.curpath = os.path.abspath(os.path.join(self.curpath, path))
            os.chdir(self.curpath)

    def get_items(self):
        filelist = os.listdir(self.curpath)
        if self.curpath != self.root_path:
            filelist.insert(0, '..')
        return [{'title': f, 'full_path': f} for f in filelist]


class TagManager:
    def __init__(self, dbpath):
        self.conn = sqlite3.connect(dbpath)
        self.curpath = '..'
        self.last_tag = None

    def get_items(self):
        with self.conn:
            cur = self.conn.cursor()
            if self.curpath == '..':
                cur.execute("SELECT * FROM tags")
                rows = cur.fetchall()
                return [{'title': t[1], 'full_path': t[1]} for t in rows]
            # else
            cur.execute("""SELECT n.title, n.full_path FROM notes AS n
                        JOIN note_tags AS nt ON (nt.note_id = n.id)
                        JOIN tags as t ON (nt.tag_id = t.id)
                        WHERE t.title = '{}'""".format(self.curpath))
            rows = cur.fetchall()
            self.last_tag = self.curpath
            return [{'title': t[0], 'full_path': t[1]} for t in rows]

    def root(self):
        self.chpath('..')

    def parent(self):
        if self.curpath == '..':
            return
        self.chpath('..')
        last, self.last_tag = self.last_tag, '..'
        return last

    def chpath(self, tag):
        if tag == '.':
            return
        self.curpath = tag


class AllManager:
    def __init__(self, dbpath):
        self.conn = sqlite3.connect(dbpath)
        self.curpath = '..'

    def get_items(self):
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT title, full_path FROM notes")
            rows = cur.fetchall()
            return [{'title': t[0], 'full_path': t[1]} for t in rows]

    def root(self): pass

    def parent(self): pass

    def chpath(self, tag): pass
