from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ItemInterface:
    """
    Base class for retrieve whole information about item.
    Using mostly by GUI module.
    Now also responsible for navigating
    id = DB pk or another way to 100% identify object and thus navigate to it
         by manager and also get all info. Single required arg
    All other will be setted as attributes
    """
    def __init__(self, item_id, kwargs):
        self.id = item_id
        kwargs = dict(kwargs) if kwargs else {}
        attrs = { col: kwargs.get(col, None) for col in self.columns }
        self.__dict__.update(attrs)

    def get_color(self): return 1
    def get_auxinfo(self) -> str: return ''
    def get_view(self): return self.title, '', self.get_size(), self.get_auxinfo()
    def get_path(self) -> str : raise NotImplemented
    def get_size(self): return 0
    def __eq__(self, other):
        if self.__class__ != other.__class__: return False
        return self.id == other.id


class TagItem(ItemInterface):
    columns = ('title', 'size',)

    def __init__(self, item_id, kwargs=None):
        super().__init__(item_id, kwargs)

    def get_size(self):
        return self.size

    def get_path(self):
        return self.title

    def get_color(self):
        return 5


class DirItem(ItemInterface):
    columns = ('title', 'size',)

    def __init__(self, dir_id, kwargs=None):
        super().__init__(dir_id, kwargs)
        if kwargs:
            self.path = self.title

    def get_size(self):
        return self.size

    def get_path(self):
        return self.title

    def get_color(self):
        return 2


class NoteItem(ItemInterface):
    columns = ('title', 'real_title', 'full_path', 'pub_date', 'mod_date', 'size', 'dir_id', 'favorite', 'status',)

    def __init__(self, item_id, kwargs=None, tags=None):
        self.favorite = False
        self.tags = tags if tags else []
        super().__init__(item_id, kwargs)
        if kwargs:
            self.path = self.full_path       #TODO: set full_path everywhere!!!!11
            if not self.real_title and self.title.find('diary_') >= 0:      # too
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
        if self.favorite:
            return 6
        elif self.real_title:
            return 3
        else:
            return 4

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

    def get_auxinfo(self):
        return ', '.join(self.tags)

    def get_view(self):
        """ View is tuple responsible to display item in ItemList """

        return (self.title, self.status, self.get_mod_date(),)


class DateItem(ItemInterface):
    def __init__(self, date_id):
        date = datetime.strptime(date_id, '%Y-%m-%dT%H:%M:%S.%fZ')


class MonthItem(ItemInterface):
    columns = ('title', 'size',)

    def __init__(self, item_id, kwargs=None):
        super().__init__(item_id, kwargs)

    def get_title(self):
        return datetime.strptime(self.title, '%Y-%m').strftime('%B %Y')

    def get_size(self):
        return self.size

    def get_path(self):
        return self.title

    def get_color(self):
        return 5

    def get_view(self):
        """ View is tuple responsible to display item in ItemList """

        return self.get_title(), '', self.get_size(), self.get_auxinfo(),
