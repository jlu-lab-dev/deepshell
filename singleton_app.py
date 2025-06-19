import logging
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtNetwork import QLocalSocket, QLocalServer, QAbstractSocket
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction

from shadow_window import ShadowWindow
from config.config_manager import ConfigManager
from utils.init_logging import setup_logging


class SingleApplication(QApplication):
    def __init__(self, argv):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        super().__init__(argv)
        self.shadow_window = None
        self.local_server = None
        self.is_running = False
        self.tray_icon = None
        self.server_name = "aiassistant"
        
        # 初始化本地连接
        self.init_local_connection()
        
        # 如果应用已经在运行，直接激活窗口并退出
        if self.is_running:
            self.activate_running_instance()
            sys.exit(0)
            
        # 只有首次运行才创建托盘和主窗口
        self.create_tray_icon()
        self.shadow_window = ShadowWindow()
        self.shadow_window.window_visible = True
 
    def init_local_connection(self):
        try:
            socket = QLocalSocket()
            socket.connectToServer(self.server_name)
            if socket.waitForConnected(500):
                self.is_running = True
                logging.info("检测到已有实例运行")
            else:
                self.is_running = False
                self.local_server = QLocalServer()
                self.local_server.newConnection.connect(self.new_local_connection)
                # 监听，如果监听失败，可能是之前程序崩溃时残留进程服务导致的，移除残留进程
                if not self.local_server.listen(self.server_name):
                    if self.local_server.serverError() == QAbstractSocket.AddressInUseError:
                        QLocalServer.removeServer(self.server_name)
                        self.local_server.listen(self.server_name)
        except Exception as e:
            logging.error(f"本地连接初始化失败: {str(e)}")
    
    def activate_running_instance(self):
        """激活已运行的实例"""
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if socket.waitForConnected(1000):
            socket.write(b"activate")
            socket.flush()
            socket.waitForBytesWritten(1000)
        socket.close()

    def new_local_connection(self):
        client_connection = self.local_server.nextPendingConnection()
        client_connection.readyRead.connect(self.handle_local_message)

    def handle_local_message(self):
        """处理来自新实例的消息"""
        try:
            client_connection = self.local_server.nextPendingConnection()
            if client_connection is None:  # 空指针检查
                logging.warning("Received invalid client connection")
                return

            # 设置超时并检查是否可读
            if not client_connection.waitForReadyRead(1000):
                logging.warning("Client connection timeout")
                client_connection.close()
                return

            # 读取消息
            msg = client_connection.readAll().data()
            if msg == b"activate":
                self.show_shadow_window()
                
        except Exception as e:
            logging.error(f"Error handling local message: {str(e)}")
        finally:
            if client_connection and client_connection.state() == QLocalSocket.ConnectedState:
                client_connection.close()

    def create_tray_icon(self):
        open_action = QAction(f"打开{ConfigManager().app_config['name']}", self)
        open_action.triggered.connect(self.show_shadow_window)

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.quit_application)

        # 右键菜单栏
        tray_menu = QMenu()
        tray_menu.addAction(open_action)
        tray_menu.addAction(exit_action)
        self.tray_icon = QSystemTrayIcon(QIcon(ConfigManager().app_config['logo']), self)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_clicked)
        self.tray_icon.show()

    def tray_icon_clicked(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # 左键
            if self.shadow_window.window_visible:
                self.shadow_window.hide()
            else:
                self.show_shadow_window()
            self.shadow_window.window_visible = not self.shadow_window.window_visible

    def show_shadow_window(self):
        if self.shadow_window is None:
            self.shadow_window = ShadowWindow()
        self.shadow_window.window_visible = True
        self.shadow_window.show()
        self.shadow_window.raise_()
        self.shadow_window.activateWindow()

    def quit_application(self):
        try:
            if self.local_server:
                self.local_server.close()
                QLocalServer.removeServer(self.server_name)
        finally:
            self.tray_icon.hide()
            QApplication.quit()


if __name__ == '__main__':
    setup_logging()

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = SingleApplication(sys.argv)
    if not app.is_running:
        app.shadow_window.show()
        sys.exit(app.exec_())
            
