from chat.chat_task import ChatTask

class TranscriptionTask(ChatTask):
    def __init__(self):
        super().__init__(assistant_type='audio_transcription')
