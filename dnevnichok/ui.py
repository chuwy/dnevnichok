import curses
import logging

from dnevnichok.aux import PagedItems
from dnevnichok.backend import GitCommandBackend
from dnevnichok.events import event_hub

logger = logging.getLogger(__name__)

backend = GitCommandBackend()


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
            return polute(view[0], self.width-16, False) + \
                   polute(view[1], 3) + \
                   polute(view[2], 12)[:self.width]
        view = item.get_view()
        if reverse:
            color = curses.color_pair(item.get_color()+12)
        else:
            color = curses.color_pair(item.get_color())
        self.scr.addstr(position, 0, render_view(view), color)
        self.on_hightlight(item=item)

        self.scr.refresh()

    def switch_items(self, items, cur_item=0):
        """ Switch items e.g. on change directory """
        start_page = cur_item // self.Y + 1
        self.cur_item = cur_item - self.Y * (cur_item // self.Y)
        self._items = PagedItems(items, self.Y, start_page)
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

    def on_hightlight(self, func=None, item=None):
        """
        With func argument it adds a callback. With item it sequentally run
        every added callback.
        """
        if func:
            self.move_callbacks.add(func)
        if item:
            for callback in self.move_callbacks:
                callback(item)

    def get_current_item(self):
        return self._items[self.cur_item]

    def process_keypress(self, c):
        if type(c) is int:                  # Arrow-keys
            if c == curses.KEY_UP:
                self.move(-1)
            elif c == curses.KEY_DOWN:
                self.move(1)
            else: return False
        elif type(c) is str:
            if c in 'lд':
                event_hub.trigger(('open', self._items[self.cur_item],))
            if c in 'hр':
                event_hub.trigger(('parent',))
            elif c in 'kл':
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
        repo_status = ''
        for s in backend.repo_status:
            repo_status += '%s ' % s
        path_length = self.width // 3 if self.width > 60 else 20
        size_length = 10
        remain = self.width - (path_length + 2 + size_length)

        self.print(polute(item.get_path(), path_length, False) +
                   polute(' ',             2) +
                   polute(item.get_size(), size_length) +
                   polute(repo_status,     remain))

    def print(self, text):
        blank = self.width - len(text)
        if text:
            self.scr.addstr(self.Y, 0, str(text) + (' '*blank), curses.color_pair(20))

    def input(self, prompt=''):
        self.print(prompt)
        curses.echo()
        self.scr.attrset(curses.color_pair(20))
        input = self.scr.getstr(self.Y, len(prompt), 40).decode('unicode_escape')
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

        curses.use_default_colors()
        curses.init_pair(1, 0, 0)
        curses.init_pair(2, 33, 0)      # dirs
        curses.init_pair(14, 0, 33)
        curses.init_pair(3, 71, 0)      # notes with titles
        curses.init_pair(15, 0, 71)
        curses.init_pair(4, 72, 0)      # notes without titles
        curses.init_pair(16, 0, 72)
        curses.init_pair(5, 99, 0)      # tags
        curses.init_pair(17, 0, 99)
        curses.init_pair(6, 184, 0)     # favorites
        curses.init_pair(18, 0, 184)

        curses.init_pair(20, 15, 234)   # bar
        self.bar = InfoBar(scr)
        stdscr_y, stdscr_x = self.stdscr.getmaxyx()
        subwin = self.stdscr.subwin(stdscr_y - 3, stdscr_x, 0, 0)

        self.left_pane = ItemList(subwin)
        self.left_pane.on_hightlight(func=self.bar.render_item_info)

        event_hub.register('print', self.print)
        event_hub.register('key-press', self.left_pane.process_keypress)
        event_hub.register('show', self.show_items)

    def print(self, text):
        self.bar.print(text)

    def input(self, prompt=None):
        return self.bar.input(prompt)

    def clear_bar(self):
        self.bar.clear()

    def show_items(self, items, cur_item=0):
        self.left_pane.switch_items(items, cur_item)
        self.left_pane.render()

    def get_current_item(self):
        return self.left_pane.get_current_item()
