from chat.chat_task import ChatTask
from mind_map.map2 import MindMapWork

class MapTask(ChatTask):
    def __init__(self):
        super().__init__(assistant_type='map')
        self.mind_map = MindMapWork()
