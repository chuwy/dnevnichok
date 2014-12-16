import logging
from os.path import join
import subprocess

from dnevnichok.config import Config

logger = logging.getLogger(__name__)
config = Config()


class GitCommandBackend:
    """
    Gives some information about file or whole repo
    """
    __shared_state = {}

    def __init__(self, path=None):
        self.__dict__ = self.__shared_state
        self.path = path if path else config.get_path('notes')
        self.status = dict()

    def get_file_mod_date(self, file_path):
        command = 'git log -1 --format="%ad" --date=iso -- ' + join(self.path, file_path)
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        date = proc.stdout.read()
        return date.decode('UTF-8').strip()

    def get_file_pub_date(self, file_path):
        command = 'git log -1 --format="%ad" --date=iso --diff-filter=A -- ' + join(self.path, file_path)
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        date = proc.stdout.read()
        return date.decode('UTF-8').strip()

    def check_status(self):
        command = 'git --git-dir={} --work-tree={} status --short'.format(
            join(self.path, '.git'), self.path
        )
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        stat = proc.stdout.read().decode('UTF-8').strip().split('\n')
        if len(stat) == 1 and stat[0] == '': return
        new_status = {}
        for line in stat:
            stat, note = line.strip().split()
            new_status.update({note: stat})
        self.status = new_status
