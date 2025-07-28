from chat.chat_task import ChatTask

class TableTask(ChatTask):
    def __init__(self):
        super().__init__(assistant_type='table')
