from chat.chat_task import ChatTask

class PPTTask(ChatTask):
    def __init__(self):
        super().__init__(assistant_type='ppt')
