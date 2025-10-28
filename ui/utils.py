from enum import Enum


class ViewMode(Enum):
    SIDEBAR = 1
    WINDOW = 2


class AssistantMode(Enum):
    """
        会议记录时AI助手为meeting模式，界面切换为meeting box，发送的消息类型MessageType是TEXT
        其他时候AI助手均为chat模式，界面切换为chat box，发送的消息可能是TEXT、IMAGE、TABLE
    """
    CHAT = "chat"
    MEETING = "meeting"
