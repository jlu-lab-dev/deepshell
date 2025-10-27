"""
主题管理器 - 支持深色和浅色主题切换
"""
from PyQt5.QtCore import QObject, pyqtSignal


class ThemeManager(QObject):
    """主题管理器单例"""
    theme_changed = pyqtSignal(str)  # 主题切换信号
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._current_theme = 'dark'  # 默认深色主题
        self._initialized = True
    
    def get_current_theme(self):
        """获取当前主题"""
        return self._current_theme
    
    def set_theme(self, theme_name):
        """设置主题"""
        if theme_name in ['dark', 'light']:
            self._current_theme = theme_name
            self.theme_changed.emit(theme_name)
    
    def toggle_theme(self):
        """切换主题"""
        new_theme = 'light' if self._current_theme == 'dark' else 'dark'
        self.set_theme(new_theme)
    
    def get_colors(self):
        """获取当前主题的颜色配置"""
        if self._current_theme == 'dark':
            return DARK_THEME
        else:
            return LIGHT_THEME


# 深色主题配色 - Cursor风格
DARK_THEME = {
    # 主背景
    'window_bg': '#1e1e1e',
    'chat_intro_bg': 'transparent',
    
    # 输入框
    'input_bg': '#2b2b2b',
    'input_border': '#3c3c3c',
    'input_text': '#cccccc',
    'input_placeholder': '#858585',
    
    # 消息气泡 - Cursor风格
    'user_message_bg': '#2b2b2b',
    'ai_message_bg': 'transparent',
    'message_text': '#cccccc',
    
    # 按钮 - Cursor风格
    'button_bg': '#2b2b2b',
    'button_hover': '#3c3c3c',
    'button_pressed': '#1e1e1e',
    'button_text': '#cccccc',
    'button_border': '#3c3c3c',
    
    # 滚动条
    'scrollbar_bg': 'transparent',
    'scrollbar_handle': '#424242',
    'scrollbar_handle_hover': '#4e4e4e',
    
    # 标题栏
    'title_text': '#cccccc',
}

# 浅色主题配色
LIGHT_THEME = {
    # 主背景
    'window_bg': '#ffffff',
    'chat_intro_bg': 'transparent',
    
    # 输入框
    'input_bg': '#f5f5f5',
    'input_border': '#e0e0e0',
    'input_text': '#1f2937',
    'input_placeholder': '#6b7280',
    
    # 消息气泡
    'user_message_bg': '#f0f0f0',
    'ai_message_bg': 'transparent',
    'message_text': '#1f2937',
    
    # 按钮
    'button_bg': '#f5f5f5',
    'button_hover': '#e8e8e8',
    'button_pressed': '#d8d8d8',
    'button_text': '#1f2937',
    'button_border': '#e0e0e0',
    
    # 滚动条
    'scrollbar_bg': 'transparent',
    'scrollbar_handle': '#d1d5db',
    'scrollbar_handle_hover': '#9ca3af',
    
    # 标题栏
    'title_text': '#1f2937',
}


def get_theme_colors(theme_name='dark'):
    """获取指定主题的颜色配置"""
    if theme_name == 'dark':
        return DARK_THEME
    else:
        return LIGHT_THEME

