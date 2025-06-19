import os
from datetime import datetime
import getpass

from PyQt5.QtCore import QThread, pyqtSignal
# import dbus
# from dbus.mainloop.glib import DBusGMainLoop
# from gi.repository import GLib
import subprocess
# from config_expired import Config


path = ""
current_user = getpass.getuser()
default_dir = '/home/' + current_user + '/.config/aiassistant/'


def signal_handler(content):
    print("revice_callback:" + content)


class MeetingTask(QThread):
    message_ready_signal = pyqtSignal(str)
    meeting_status_signal = pyqtSignal(str)

    def __init__(self):
        super(MeetingTask, self).__init__()
        self.status = ""
        # DBusGMainLoop(set_as_default=True)
        # self.bus = dbus.SessionBus()  # 或 dbus.SessionBus()，取决于你的服务在哪里运行

    def message_signal_handler(self, message):
        self.message_ready_signal.emit(message)
        print("message_signal_handler:" + message)

    def status_signal_handler(self, message):
        # self.meeting_status_signal.emit(message)
        if message == "AccessKeyId is mandatory for this action.":
            message = "云端AI模型接口连接失败，请检查设置信息后重试。"
            print("status_signal_handler:" + message)

    def stop(self):
        print("stop")

    def close_bin_process(self):
        # process = subprocess.Popen(["killall", "RealTimeMeeting"])
        os.system("killall RealTimeMeeting")

    def exec_bin_process(self):
        # process = subprocess.Popen(["/bin/sh", "-c", "/usr/share/aiassistant/RealTimeMeeting"])
        process = subprocess.Popen(["/usr/share/aiassistant/bin/RealTimeMeeting"])

    def meeting_init(self):
        bus = dbus.SessionBus()
        meetingObj = bus.get_object('com.deepshell.aiassistant', '/')
        meetingInterface = dbus.Interface(meetingObj, 'com.deepshell.aiassistant.meetinginterface')
        meetingInterface.Init(Config.get_app_key(), Config.get_ALIBABA_CLOUD_ACCESS_KEY_ID(), Config.get_ALIBABA_CLOUD_ACCESS_KEY_SECRET())

    def start_task(self):
        self.meeting_init()
        bus = dbus.SessionBus()
        meetingObj = bus.get_object('com.deepshell.aiassistant', '/')
        meetingInterface = dbus.Interface(meetingObj, 'com.deepshell.aiassistant.meetinginterface')
        meetingInterface.StartMeetingService()
        result = meetingInterface.GetTaskStatus()
        if not result:
            message = "云端AI模型接口连接失败，请检查设置信息后重试。"
            self.message_ready_signal.emit(message)

    def stop_task(self):
        bus = dbus.SessionBus()
        meetingObj = bus.get_object('com.deepshell.aiassistant', '/')
        meetingInterface = dbus.Interface(meetingObj, 'com.deepshell.aiassistant.meetinginterface')
        meetingInterface.StopMeetingService()
        self.close_bin_process()
        # 获取会议纪要文件
        meeting_file = MeetingFile.get_current_meeting_file()
        # 判断文件是否为空
        if os.path.exists(meeting_file):
            message = "您已结束会议，会议纪要文件" + meeting_file + "已生成，详情请点击下方按钮查看。"
            self.message_ready_signal.emit(message)


    def run(self):

        # 假设服务的名称是 org.freedesktop.DBus.ExampleService，对象路径是 /org/freedesktop/DBus/ExampleObject，接口是 org.freedesktop.DBus.Example
        proxy_obj = self.bus.get_object('com.deepshell.aiassistant', '/')
        iface = dbus.Interface(proxy_obj, 'com.deepshell.aiassistant.meetinginterface')

        # 连接信号到处理函数
        # iface.connect_to_signal("MessageReady", signal_handler)

        self.bus.add_signal_receiver(self.message_signal_handler, signal_name='MessageReady',
                                dbus_interface='com.deepshell.aiassistant.meetinginterface',
                                bus_name='com.deepshell.aiassistant', path='/')

        self.bus.add_signal_receiver(self.status_signal_handler, signal_name='ServiceStatus',
                                dbus_interface='com.deepshell.aiassistant.meetinginterface',
                                bus_name='com.deepshell.aiassistant', path='/')

        # 开始主循环
        self.mainloop = GLib.MainLoop()
        self.mainloop.run()


class MeetingFile:

    @staticmethod
    def crate_temp_file():
        global default_dir
        global path
        if not os.path.exists(default_dir):
            print("目录：" + default_dir + " 不存在")
            os.mkdir(default_dir)

        now = datetime.now()
        filename = now.strftime('%Y-%m-%d-%H-%M-%s') + ".txt"

        path = default_dir + filename
        print(path)


    @staticmethod
    def write_temp_file(content):
        global path
        print(path)
        with open(path, 'a', encoding='utf-8') as file:
            file.write(content+"\n")
            file.flush()


    @staticmethod
    def open_file(filename):
        process = subprocess.Popen(["featherpad", filename])


    @staticmethod
    def get_default_dir():
        global default_dir
        return default_dir

    @staticmethod
    def get_current_meeting_file():
        global path
        return path
