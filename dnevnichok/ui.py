#!/usr/bin/env python3

import curses

from dnevnichok.aux import PagedItems, EventQueue


class ItemList:
    """
    Pane with list of dirs, tags, files or god knows what else
    """
    def __init__(self, scr, items):
        self.scr = scr
        self.Y, self.X = self.scr.getmaxyx()
        self.cur_item = 0
        self._items = PagedItems(items, self.Y)
        self.length = len(self._items)
        self.width = 50

    def render(self):
        """ Render new state """
        self.scr.clear()
        self.length = len(self._items)
        for i, item in enumerate(self._items):
            if i == self.cur_item: self.render_item(i, item, True)
            elif i >= self.Y: break
            else: self.render_item(i, item)

    def render_item(self, position, item, reverse=False):
        if reverse:
            self.scr.addstr(position, 0, item['title'][:self.width], curses.A_REVERSE)
        else:
            self.scr.addstr(position, 0, item['title'][:self.width])
        self.scr.refresh()

    def switch_items(self, items, cur_item=0):
        """ Switch items e.g. on change directory """
        self.cur_item = cur_item
        self._items = PagedItems(items, self.Y)
        self.scr.clear()
        self.render()

    def move_highlight(self, to):
        self.render_item(self.cur_item, self._items[self.cur_item])
        self.render_item(to, self._items[to], True)

    def move(self, i):
        if i > 0 and self.cur_item < self.length-1:     # Down
            self.move_highlight(self.cur_item+i)
            self.cur_item += i
        elif i > 0 and self.cur_item == self.length-1 and not self._items.has_next():
            curses.beep()
        elif i > 0 and self.cur_item == self.length-1 and self._items.has_next():
            self.cur_item = 0
            self._items.next()
            self.render()
        elif i < 0 and self.cur_item > 0:               # Up
            self.move_highlight(self.cur_item+i)
            self.cur_item += i  # i is negative
        elif i < 0 and self.cur_item == 0 and not self._items.has_prev():
            curses.beep()
        elif i < 0 and self.cur_item == 0 and self._items.has_prev():
            self.cur_item = self.length-1
            self._items.prev()
            self.render()

    def move_to(self, i):
        if i < 0:
            i = self.length - i - 2
        self.move_highlight(i)
        self.cur_item = i

    def process_keypress(self, c):
        if type(c) is int:                  # Arrow-keys
            if c == curses.KEY_UP:
                self.move(-1)
            elif c == curses.KEY_DOWN:
                self.move(1)
        elif type(c) is str:
            if c in 'lд':
                EventQueue.push(('open', self._items[self.cur_item],))
            if c in 'hр':
                EventQueue.push(('parent',))
            elif c in 'kл':         # Movements
                self.move(-1)
            elif c in 'jо':
                self.move(1)
            elif c in 'G':
                self.move_to(-1)
            else:
                pass
