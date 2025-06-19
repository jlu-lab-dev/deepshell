import os
import subprocess
import sys
from PyQt5.QtCore import QThread


class OpenLocalAppTask(QThread):
    def __init__(self):
        super(OpenLocalAppTask, self).__init__()
        self.app = ""

    def set_app(self, app):
        self.app = app + " &"

    def run(self):
        process = subprocess.Popen(self.app, shell=True)
        # process.wait()
        #
        # print(process.returncode)

        # os.system(self.app)
        print("已打开:" + self.app)




