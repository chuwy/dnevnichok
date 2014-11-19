from os.path import join
import subprocess

class GitCommandBackend:
    """
    Gives some information about file or whole repo
    """
    def __init__(self, path=None):
        self.path = path

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
