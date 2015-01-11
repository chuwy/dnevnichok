from collections import UserList


class PagedItems(UserList):
    """ Stores everything, but only one page (slice) available at the moment"""
    def __init__(self, initlist=None, lines=None, start_page=1):
        if not lines:
            raise TypeError("You must provide lines arg")
        else:
            self._lines = lines     # how much element are shown
        super().__init__(initlist)
        self._unpaged = True
        self.page = start_page
        self.set_page(self.page)

    def set_page(self, page):
        self.page = page
        if self._unpaged:
            self._full_data = self.data
            self._unpaged = False
        self.data = self._full_data[(self.page-1)*self._lines:self.page*self._lines]

    def set_lines(self, lines):
        self._lines = lines
        self.set_page(self.page)

    def next(self):
        self.set_page(self.page+1)

    def prev(self):
        self.set_page(self.page-1)

    def has_next(self):
        return len(self._full_data) > self.page*self._lines

    def has_prev(self):
        return self.page > 1
