#!/usr/bin/env python3

"""
Module contain one-run procedures and helpers for parse whole library
"""

import os
import sqlite3
from collections import deque
from docutils.core import publish_doctree
from docutils.utils import SystemMessage

from dnevnichok.helpers import get_config

class TagsCache:
    def __init__(self):
        self.cache = {}

    def set(self, key, value):
        if key not in self.cache:
            self.cache[key] = value
        else:
            pass

class NoteInfo:
    def __init__(self):
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


def parse_note(path):
    with open(path, 'r') as f:
        note_info = NoteInfo()
        note_info.path = path

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


def get_notes(notespath):
    notes = []
    for path, subdirs, files in os.walk(notespath):
        for name in (f for f in files if f.endswith(".rst")):
            try:
                notes.append(parse_note(os.path.join(path, name)))
            except UnicodeDecodeError:
                print('so here is unicode error: ' + os.path.join(path, name))
            except SystemMessage:
                print('and here is other error: ' + os.path.join(path, name))
    return notes


def populate_db_with_dirs(notespath, dbpath):
    """ First candidate to unit testing """
    def list_dir(path):
        mapped = map(lambda x: os.path.join(path, x), os.listdir(path))
        filtered = filter(lambda i: i.find('/.git') < 0 and os.path.isdir(i), mapped)
        return list(filtered)

    def get_dirs(dirs):
        """
        Recursive function with conjection with list_dir
        gives us whole flat tree structure of directories
        Remainder: recursion in python is ugly, at least need to write generator
        """
        if len(dirs) == 0: return []
        if len(dirs) == 1:
            return [dirs[0]] + get_dirs(list_dir(dirs[0]))
        else:
            return [dirs[0]] + get_dirs(list_dir(dirs[0])) + get_dirs(dirs[1:])

    os.chdir(notespath)
    dirs = get_dirs(list_dir('.'))

    conn = sqlite3.connect(dbpath)
    with conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS dirs")
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


def populate_db(notes, dbpath):
    tags_cache = {}
    conn = sqlite3.connect(dbpath)
    with conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS tags")
        cur.execute("DROP TABLE IF EXISTS notes")
        cur.execute("DROP TABLE IF EXISTS note_tags")

        cur.execute("""CREATE TABLE IF NOT EXISTS
                       tags(id INTEGER PRIMARY KEY, title TEXT UNIQUE)""")

        cur.execute("""CREATE TABLE IF NOT EXISTS
                       notes(id INTEGER PRIMARY KEY, title TEXT, real_title INTEGER, full_path TEXT, pub_date TEXT, mod_date TEXT, size INT, dir_id INTEGER,
                       FOREIGN KEY(dir_id) REFERENCES dirs(id))""")

        cur.execute("""CREATE TABLE IF NOT EXISTS
                       note_tags(note_id INTEGER, tag_id INTEGER,
                       FOREIGN KEY(note_id) REFERENCES notes(id), FOREIGN KEY(tag_id) REFERENCES tags(id))""")

        for note in notes:
            cur.execute("INSERT INTO notes(title, real_title, full_path, size) VALUES(?, ?, ?, ?)", (note.get_title(), note.real_title, note.path, note.get_size()))
            note.id = cur.lastrowid
            for tag in note.tags:
                cur.execute("INSERT OR IGNORE INTO tags(title) VALUES(?)", (tag,))
                if tag not in tags_cache:
                    tags_cache[tag] = cur.lastrowid
                cur.execute("INSERT INTO note_tags(note_id, tag_id) VALUES(?, ?)", (note.id, tags_cache[tag],))


def repopulate_db():
    config = get_config()
    dbpath = os.path.abspath(os.path.expanduser(config.get('Paths', 'db')))
    notespath = os.path.abspath(os.path.expanduser(config.get('Paths', 'notes')))

    populate_db_with_dirs(notespath, dbpath)
    notes = get_notes(notespath)
    populate_db(notes, dbpath)
