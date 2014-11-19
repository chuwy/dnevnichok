#!/usr/bin/env python3

"""
Module contain one-run procedures and helpers for parse whole library
"""

from collections import deque, OrderedDict
from docutils.core import publish_doctree
from docutils.utils import SystemMessage
import logging
import os
from os.path import join, isdir
import sqlite3

from dnevnichok.helpers import get_config
from dnevnichok.backend import GitCommandBackend

logging.basicConfig(filename='noter.log')

try:
    import colored_traceback
    colored_traceback.add_hook()
except ImportError:
    pass


config = get_config()
dbpath = os.path.abspath(os.path.expanduser(config.get('Paths', 'db')))
notespath = os.path.abspath(os.path.expanduser(config.get('Paths', 'notes')))
repo = GitCommandBackend(notespath)


class NoteInfo:
    def __init__(self, dir_id):
        self.dir_id = dir_id
        self.title = None
        self.real_title = False
        self.tags = []

    def set_title(self, title):
        if title:
            self.title = title
            self.real_title = True

    def get_title(self):
        if not self.title:
            return self.get_filename()
        else:
            return self.title

    def get_filename(self):
        return os.path.basename(self.path)

    def get_size(self):
        return os.path.getsize(self.path)

    def __str__(self):
        if self.tags:
            return "\"{}\" with {} in {} {}".format(self.get_title(), ', '.join(self.tags), self.path, self.get_size())
        else:
            return "{} without tags in {}".format(self.get_title(), self.path)


def parse_note(path, dir_id):
    with open(path, 'r') as f:
        note_info = NoteInfo(dir_id)
        note_info.path = path
        note_info.mod_date = repo.get_file_mod_date(path)
        note_info.pub_date = repo.get_file_pub_date(path)

        dom = publish_doctree(f.read(),
                              settings_overrides={'halt_level': 2,
                                                  'traceback': True,
                                                  'syntax_highlight': 'none'
                                                  }).asdom()
        note_info.set_title(dom.firstChild.getAttribute('title'))

        fields = dom.getElementsByTagName('field')
        for field in fields:
            if field.getElementsByTagName('field_name')[0].firstChild.nodeValue == 'tags':
                tags_line = field.getElementsByTagName('field_body')[0].childNodes[0].firstChild.nodeValue
                note_info.tags = tags_line.split(', ')

        return note_info


def pollute_dirs_and_notes(notespath, dbpath):
    class MutableInt:
        i = 1
        def save(self, i): self.i = i
    root_dir = MutableInt()     # Store last inserted dir (lastrowid polluting by dirs_path's INSERTs
    added_roots = OrderedDict() # Cache for all inserted directories
    exclude = set(['.git'])

    def add_d(path, cur):
        """ Accepts path to dir and saves all it's parents"""
        path_listed = path.split('/')

        content = filter(lambda p: isdir(join(path,p)) or p.endswith('.rst'), os.listdir(path))
        size = len(list(content))

        def get_full_path(current_name, depth):
            """ Get directory from listed path by specified depth """
            if depth == 0: return current_name
            else: return '/'.join(path_listed[:depth]) + '/' + current_name
        def get_all_parents(full_path):
            """ Return list of ids for all parent directories """
            parents = []
            cur_path = full_path
            for d, parent in enumerate(full_path.split('/')[:-1]):
                cur_path = os.path.dirname(cur_path)
                parents.append(cur_path)
            return map(lambda p: added_roots[p], parents)

        for depth, dir_name in enumerate(path_listed):
            cur_full_path = get_full_path(dir_name, depth)
            if cur_full_path not in added_roots:
                cur.execute("""INSERT INTO dirs(title, size)
                               VALUES(?, ?)""",
                               (dir_name, size))
                added_roots.update({path: cur.lastrowid})       # ok, we've inserted this path
                root_dir.save(cur.lastrowid)                    # root_dir = lastrowid
                cur.execute("""INSERT INTO dirs_path(ancestor, descendant, direct)
                               VALUES(?, ?, ?)""",
                               (cur.lastrowid, cur.lastrowid, False,)) # insert self-reference first

            for d, parent_id in enumerate(get_all_parents(cur_full_path)):    # inserts all parent dirs as ancestors
                direct = True if d == 0 else False
                cur.execute("""INSERT OR IGNORE INTO dirs_path(ancestor, descendant, direct)
                               VALUES(?, ?, ?)""",
                               (parent_id, root_dir.i, direct,))


    conn = sqlite3.connect(dbpath)
    with conn:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS
                       dirs(id INTEGER PRIMARY KEY, title TEXT, size INTEGR)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS
                       dirs_path (ancestor INTEGER, descendant INTEGER, direct INTEGER,
                       PRIMARY KEY (ancestor, descendant))""")

        os.chdir(notespath)
        notes = []
        for root, dirs, files in os.walk('.', topdown=True):
            dirs[:] = [d for d in dirs if d not in exclude]
            add_d(root, cur)
            for f in filter(lambda x: x.endswith('.rst'), files):
                try:
                    notes.append(parse_note(join(root, f), root_dir.i))
                except UnicodeDecodeError:      # TODO: add error to DB
                    logging.warn("so here is unicode error: " + join(root, f))
                except SystemMessage:
                    logging.warn("and here is other error: " + join(root, f))

    populate_db_with_notes(notes, notespath, dbpath)


def get_notes(notespath):
    notes = []
    for path, subdirs, files in os.walk(notespath):
        for name in (f for f in files if f.endswith(".rst")):
            try:
                notes.append(parse_note(join(path, name)))
            except UnicodeDecodeError:
                print("so here is unicode error: " + join(path, name))
            except SystemMessage:
                print("and here is other error: " + join(path, name))
    return notes


def populate_db_with_dirs(notespath, dbpath):
    """ First candidate to unit testing """
    # TODO: remove
    def list_dir(path):
        mapped = map(lambda x: join(path, x), os.listdir(path))
        filtered = filter(lambda i: i.find('/.git') < 0 and isdir(i), mapped)
        return list(filtered)

    def get_dirs(dirs):
        """
        Recursive function with conjection with list_dir
        gives us whole flat tree structure of directories
        Remainder: recursion in python is ugly, at least need to write generator
        """
        if len(dirs) == 0:
            return []
        if len(dirs) == 1:
            return [dirs[0]] + get_dirs(list_dir(dirs[0]))
        else:
            return [dirs[0]] + get_dirs(list_dir(dirs[0])) + get_dirs(dirs[1:])

    os.chdir(notespath)
    dirs = get_dirs(list_dir('.'))

    conn = sqlite3.connect(dbpath)
    with conn:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS
                       dirs(id INTEGER PRIMARY KEY, title TEXT, parent_dir_id INT,
                       UNIQUE (title, parent_dir_id),
                       FOREIGN KEY(parent_dir_id) REFERENCES dirs(id))""")
        cur.execute("INSERT INTO dirs(title) VALUES('.')")
        for full_dir in dirs:
            for depth, sub_dir in enumerate(full_dir.split('/')):
                if sub_dir == '.':
                    parent = None
                    continue
                elif depth == 1:
                    parent = 1
                else:
                    parent_dir = full_dir.split('/')[depth-1]
                    cur.execute("""SELECT id FROM dirs WHERE title = '{}'
                                   ORDER BY id ASC LIMIT 1""".format(parent_dir))
                    parent = cur.fetchone()[0]
                cur.execute("""INSERT OR IGNORE INTO dirs(title, parent_dir_id)
                               VALUES(?, ?)""", (sub_dir, parent))


def populate_db_with_notes(notes, notespath, dbpath):
    tags_cache = {}
    conn = sqlite3.connect(dbpath)

    with conn:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS
                       tags(id INTEGER PRIMARY KEY, title TEXT UNIQUE)""")

        cur.execute("""CREATE TABLE IF NOT EXISTS
                       notes(id INTEGER PRIMARY KEY, title TEXT, real_title INTEGER, full_path TEXT, pub_date TEXT, mod_date TEXT, size INT, dir_id INTEGER,
                       FOREIGN KEY(dir_id) REFERENCES dirs(id))""")

        cur.execute("""CREATE TABLE IF NOT EXISTS
                       note_tags(note_id INTEGER, tag_id INTEGER,
                       FOREIGN KEY(note_id) REFERENCES notes(id), FOREIGN KEY(tag_id) REFERENCES tags(id))""")

        for note in notes:
            cur.execute("""INSERT INTO notes(title, real_title, full_path, pub_date, mod_date, size, dir_id)
                           VALUES(?, ?, ?, ?, ?, ?, ?)""",
                           (note.get_title(), note.real_title, note.path, note.pub_date, note.mod_date, note.get_size(), note.dir_id))
            note.id = cur.lastrowid
            for tag in note.tags:
                cur.execute("INSERT OR IGNORE INTO tags(title) VALUES(?)", (tag,))
                if tag not in tags_cache:
                    tags_cache[tag] = cur.lastrowid
                cur.execute("INSERT INTO note_tags(note_id, tag_id) VALUES(?, ?)", (note.id, tags_cache[tag],))


def repopulate_db():
    conn = sqlite3.connect(dbpath)
    with conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS notes")
        cur.execute("DROP TABLE IF EXISTS tags")
        cur.execute("DROP TABLE IF EXISTS note_tags")
        cur.execute("DROP TABLE IF EXISTS dirs_path")
        cur.execute("DROP TABLE IF EXISTS dirs")

    pollute_dirs_and_notes(notespath, dbpath)


if __name__ == '__main__':
    repopulate_db()
