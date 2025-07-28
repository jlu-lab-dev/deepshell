from chat.chat_task import ChatTask

class OcrTask(ChatTask):
    def __init__(self):
        super().__init__(assistant_type='ocr')
