from datetime import datetime
import curses
import os
import logging

logger = logging.getLogger(__name__)


class ItemInterface:
    """
    Base class for retrieve whole information about item.
    Using mostly by GUI module.
    Now also responsible for navigating
    id = DB pk or another way to 100% identify object and thus navigate to it
         by manager and also get all info. Single required arg
    title = will be named almost everywhere
    path? = used by chpath() in managers if id isn't appropriate
    name_  = filename if need
    size!
    color
    """
    def __init__(self, item_id, **kwargs):
        self.id = item_id
        self.__dict__.update(kwargs)

    def get_view(self):
        return (self.title, self.get_size())

    def get_color(self): return curses.color_pair(3)
    def __repr__(self): return self.category + ' ' + self.title
    def __eq__(self, other):
        if self.category != other.category: return False
        return self.id == other.id


class TagItem(ItemInterface):
    category = 'tag'

    def get_size(self):
        return self.size

    def get_path(self):
        return self.title

    def get_color(self):
        return curses.color_pair(4)


class DirItem(ItemInterface):
    category = 'dir'

    def get_size(self):
        return self.size

    def get_path(self):
        return self.title

    def get_color(self):
        return curses.color_pair(5)


class NoteItem(ItemInterface):
    category = 'note'

    def __init__(self, item_id, **kwargs):
        super().__init__(item_id, **kwargs)
        if not self.real_title and self.title.find('diary_') >= 0:
            try:
                self.title = datetime.strptime(self.title, 'diary_%d-%m-%Y.rst').strftime('Дневничок от %d %B %Y')
            except ValueError:
                pass

    def get_size(self):
        return self.size

    def get_path(self):
        if self.path.startswith('./'):
            return self.path[2:]
        else:
            return self.path

    def get_color(self):
        if self.real_title:
            return curses.color_pair(6)
        else:
            return curses.color_pair(2)

    def get_mod_date(self):
        try:
            date = datetime.strptime(self.mod_date, '%Y-%m-%d %H:%M:%S %z')
        except ValueError: return ''
        return date.strftime('%d %b %y')

    def get_pub_date(self):
        try:
            date = datetime.strptime(self.pub_date, '%Y-%m-%d %H:%M:%S %z')
        except ValueError: return ''
        return date.strftime('%d %b %y')

    def get_view(self):
        return (self.title, self.get_mod_date())


class DateItem(ItemInterface):
    category = 'date'

    def __init__(self, date_id):
        date = datetime.strptime(date_id, '%Y-%m-%dT%H:%M:%S.%fZ')


def Item(path, hint=None):
    """
    Item factory function. Decides which category current item belongs.
    If item match no criteria it returns None and can be considered to filter
    out this item.
    """
    if hint:
        if hint == 'tag':   return TagItem(path)
        if hint == 'dir':   return DirItem(path)
        if hint == 'date':  return DateItem(path)
        if hint == 'note':  return NoteItem(path)

    return DirItem(path)
