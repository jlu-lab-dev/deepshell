#import langid
from translation.language_dic import dic
from chat.assistant import *

class TranslateDetect:
    def __init__(self):
        super().__init__()
    @staticmethod
    def detect_language(topic:str):
        if not topic.strip():
            return 'unknown'

        try:
            response = None

            assistant = Assistant("Translate")
            messages = [f'你需要识别我传入语句的语种，语种用ISO639-1语言列表的标准告知我，\
                     回复我的格式是：语种：XXX，当你不能识别出语种时，XX处替换为unknown，\
                     我现在传入的语句是'+topic]
            response = assistant.chat(messages)

            return dic[response.split('：')[1].lower()]
        except Exception as e:
            print(f"语种检测调用 异常: {e}")
            return "request exception."

    # @staticmethod
    # def detect_language_without_api(topic:str):
    #     #topic：用户输入对话框的语种
    #
    #     #输入为空
    #     if not topic.strip():
    #         return 'unknown'
    #
    #     #检测范围：英语、中文、法语、德语、日语、俄语、韩语
    #     langid.set_languages(['en','zh','fr','de','ja','ru','ko'])
    #
    #     lang,confident=langid.classify(topic)
    #     #还没有实现无意义语段识别
    #     return language_dic.dic[lang]# if confident>0.3 else "unknown"


if  __name__ == '__main__':
    print(TranslateDetect.detect_language('测试'))
