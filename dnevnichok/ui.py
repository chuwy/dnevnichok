#!/usr/bin/env python3

import curses
import logging

from dnevnichok.aux import PagedItems, EventQueue


def polute(text, width, begin=True):
    """ Adds spaces to begin or end of line """
    text = str(text)
    text_len = len(text)
    if text_len >= width:
        return text[:width]
    else:
        remain = ' ' * (width - text_len)
        if begin:
            return remain + text
        else:
            return text + remain


class ItemList:
    """
    Pane with list of dirs, tags, files or god knows what else
    TODO: Initialize empty
    """
    def __init__(self, scr, items=None):
        self.scr = scr
        self.Y, self.X = self.scr.getmaxyx()
        self.cur_item = 0
        self._items = PagedItems(items, self.Y)
        self.length = len(self._items)
        self.width = self.X

        self.move_callbacks = set()

    def render(self):
        """ Render new state """
        self.scr.clear()
        self.length = len(self._items)
        for i, item in enumerate(self._items):
            if i == self.cur_item: self.render_item(i, item, True)
            elif i >= self.Y: break
            else: self.render_item(i, item)

    def render_item(self, position, item, reverse=False):
        def render_view(view):
            return polute(view[0], self.width-20, False) + polute(view[1], 12)[:self.width]
        view = item.get_view()
        if reverse:
            self.scr.addstr(position, 0, render_view(view), curses.A_REVERSE)
            self.onHightlight(item=item)
        else:
            self.scr.addstr(position, 0, render_view(view), item.get_color())
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
            return
        elif i > 0 and self.cur_item == self.length-1 and self._items.has_next():
            self.cur_item = 0
            self._items.next()
            self.render()
        elif i < 0 and self.cur_item > 0:               # Up
            self.move_highlight(self.cur_item+i)
            self.cur_item += i  # i is negative
        elif i < 0 and self.cur_item == 0 and not self._items.has_prev():
            curses.beep()
            return
        elif i < 0 and self.cur_item == 0 and self._items.has_prev():
            self.cur_item = self.length-1
            self._items.prev()
            self.render()

    def move_to(self, i):
        if i < 0:
            i = self.length - i - 2
        self.move_highlight(i)
        self.cur_item = i

    def onHightlight(self, func=None, item=None):
        """
        With func argument it adds a callback. With item it sequentally run
        every added callback.
        """
        if func:
            self.move_callbacks.add(func)
        if item:
            for callback in self.move_callbacks:
                callback(item)

    def process_keypress(self, c):
        if type(c) is int:                  # Arrow-keys
            if c == curses.KEY_UP:
                self.move(-1)
            elif c == curses.KEY_DOWN:
                self.move(1)
            else: return False
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
            else: return False
        else: return False
        return True


class InfoBar:
    def __init__(self, scr):
        self.scr = scr
        height, self.width = self.scr.getmaxyx()
        self.Y = height - 2

    def render_item_info(self, item):
        self.print(polute(item.get_size(), 8) +
                   polute(' ', 2) +
                   polute(item.get_path(), 30))

    def print(self, text):
        if text:
            self.scr.addstr(self.Y, 1, str(text))

    def input(self, prompt=''):
        curses.echo()
        self.print(prompt)
        input = self.scr.getstr(self.Y, len(prompt), 20).decode('unicode_escape')
        curses.noecho()
        self.clear()
        return input

    def clear(self):
        self.scr.move(self.Y, 0)
        self.scr.clrtoeol()


class MainWindow:
    def __init__(self, scr):
        self.stdscr = scr
        self.stdscr.clear()
        curses.curs_set(0)
        if curses.has_colors():
            curses.init_pair(1, curses.COLOR_BLUE, 0)
            curses.init_pair(2, curses.COLOR_CYAN, 0)
            curses.init_pair(3, curses.COLOR_GREEN, 0)
            curses.init_pair(4, curses.COLOR_MAGENTA, 0)
            curses.init_pair(5, curses.COLOR_RED, 0)
            curses.init_pair(6, curses.COLOR_YELLOW, 0)
            curses.init_pair(7, curses.COLOR_WHITE, 0)
        self.bar = InfoBar(scr)
        stdscr_y, stdscr_x = self.stdscr.getmaxyx()
        subwin = self.stdscr.subwin(stdscr_y - 3, stdscr_x, 0, 0)

        self.left_pane = ItemList(subwin)
        self.left_pane.onHightlight(func=self.bar.render_item_info)

    def print(self, text):
        self.bar.print(text)

    def input(self, prompt=None):
        return self.bar.input(prompt)

    def clear_bar(self):
        self.bar.clear()

    def show_items(self, items, cur_item=0):
        self.left_pane.switch_items(items, cur_item)
        self.left_pane.render()

    def process_keypress(self, c):
        return self.left_pane.process_keypress(c)
