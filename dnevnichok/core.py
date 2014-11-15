import os

# TODO: it can be a very bad idea to recreate db connection on each item render,
# so do not forget you may be be forced to reuse it.

class ItemInterface:
    """
    Base class for retrieve whole information about item.
    Using mostly by GUI module.
    """
    def __init__(self, path): raise NotImplementedError
    def size(self): raise NotImplementedError
    def title(self): raise NotImplementedError
    def __repr__(self): return self.category + ' ' + self.title
    def __eq__(self, other):
        if self.category != other.category: return False
        return self.full_path == other.full_path


class TagItem(ItemInterface):
    category = 'tag'

    def __init__(self, path):
        self.title = path
        self.full_path = path

    def size(self):
        return 33


class DateItem(ItemInterface):
    category = 'date'

    def __init__(self, path):
        date = datetime.strptime(path, '%Y-%m-%dT%H:%M:%S.%fZ')


class DirItem(ItemInterface):
    category = 'dir'

    def __init__(self, path):
        self.title = os.path.basename(path)
        self.full_path = path

    def size(self):
        all_dirs = os.listdir(self.full_path)
        filtered = filter(lambda f: not f.startswith('.'), all_dirs)
        return len(list(filtered))


class NoteItem(ItemInterface):
    category = 'note'

    def __init__(self, path):
        self.title = os.path.basename(path)
        self.full_path = path

    def size(self):
        return os.path.getsize(self.full_path)


def Item(path, hint=None):
    """
    Item factory function. Decides which category current item belongs.
    If item match no criteria it returns None and can be considered to filter
    out this item.
    """
    if hint and hint == 'tag' and not os.path.isdir(path):
        return TagItem(path)
    if os.path.isfile(path) and path.endswith('.rst'):
        return NoteItem(path)
    elif os.path.isdir(path):
        return DirItem(path)
    else:
        try:
            return DateItem(path)
        except ValueError:
            pass
