
        self.tray_icon = QSystemTrayIcon(QIcon(ConfigManager().app_config['logo']), self)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_clicked)