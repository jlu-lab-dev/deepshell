import re
import json
from ppt.makePPTByTemplate.ppt_creator import PPTCreator
import os
import datetime
from PyQt5.QtCore import QObject, pyqtSignal

class PPTGenerator(QObject):
    pptgen_complete_signal = pyqtSignal(str)  # 用于通知完成
    def __init__(self ):
        super().__init__()

    def clean_content(self,content):
        """去除内容中的多余空格"""
        return ' '.join(content.split()).strip()


    def markdown_to_json(self,markdown_text):
        # 初始化结果字典
        result = {
            "ppt_title": {"description": ""},
            "structure": {
                "introduction": {"description": ""},
                "topics": {"count": 0, "each_topic": []},
                "conclusion": {"sections": {"count": 0, "each_section": []}}
            }
        }

        lines = [line.strip() for line in markdown_text.split('\n') if line.strip()]
        i = 0
        n = len(lines)

        def is_topic(line):
            return (line.startswith('## ') and
                    not line.startswith('## 引文') and
                    not line.startswith('## 总结'))

        # 提取标题
        while i < n and not lines[i].startswith('# '):
            i += 1
        if i < n:
            result["ppt_title"]["description"] = self.clean_content(lines[i].replace('# ', ''))
            i += 1

        # 提取引言
        while i < n and not lines[i].startswith('## 引文'):
            i += 1
        if i < n:
            i += 1
            intro_lines = []
            while i < n and not is_topic(lines[i]) and not lines[i].startswith('## 总结'):
                intro_lines.append(self.clean_content(lines[i]))
                i += 1
            result["structure"]["introduction"]["description"] = ' '.join(intro_lines)

        # 处理主题
        topics = []
        while i < n and not lines[i].startswith('## 总结'):
            if is_topic(lines[i]):
                topic = {
                    "name": self.clean_content(lines[i].replace('## ', '')),
                    "subtopics": {"count": 0, "each_subtopic": []}
                }
                i += 1

                # 处理子主题
                subtopics = []
                while i < n and lines[i].startswith('### '):
                    subtopic = {
                        "name": self.clean_content(lines[i].replace('### ', '')),
                        "sections": {"count": 0, "each_section": []}
                    }
                    i += 1

                    # 处理章节
                    sections = []
                    while i < n and lines[i].startswith('#### '):
                        section = {
                            "title": self.clean_content(lines[i].replace('#### ', '')),
                            "content": ""
                        }
                        i += 1

                        # 获取章节内容
                        content_lines = []
                        while i < n and not (lines[i].startswith('#### ') or
                                            lines[i].startswith('### ') or
                                            lines[i].startswith('## ')):
                            content_lines.append(self.clean_content(lines[i]))
                            i += 1

                        section["content"] = ' '.join(content_lines)
                        sections.append(section)

                    subtopic["sections"]["each_section"] = sections
                    subtopic["sections"]["count"] = len(sections)
                    subtopics.append(subtopic)

                topic["subtopics"]["each_subtopic"] = subtopics
                topic["subtopics"]["count"] = len(subtopics)
                topics.append(topic)
            else:
                i += 1

        result["structure"]["topics"]["each_topic"] = topics
        result["structure"]["topics"]["count"] = len(topics)

        # 处理总结
        while i < n and not lines[i].startswith('## 总结'):
            i += 1
        if i < n:
            i += 1
            sections = []
            while i < n and lines[i].startswith('### '):
                section = {
                    "title": self.clean_content(lines[i].replace('### ', '')),
                    "content": ""
                }
                i += 1

                content_lines = []
                while i < n and not (lines[i].startswith('### ') or lines[i].startswith('## ')):
                    content_lines.append(self.clean_content(lines[i]))
                    i += 1

                section["content"] = ' '.join(content_lines)
                sections.append(section)

            result["structure"]["conclusion"]["sections"]["each_section"] = sections
            result["structure"]["conclusion"]["sections"]["count"] = len(sections)

        self.json_to_ppt(result)

    def json_to_ppt(self,data):
        curpath = os.path.dirname(os.path.abspath(__file__))
        template_dir = os.path.join(curpath, "ppt_templates", "default")
        creator = PPTCreator(template_dir=template_dir)
        # 1. 添加标题页 - 从字典中提取description
        creator.add_title_slide(data["ppt_title"]["description"])
        # 2. 添加目录页
        topic_names = [topic["name"] for topic in data["structure"]["topics"]["each_topic"]]
        creator.add_contents_slide(topic_names)
        # 3. 添加引文页
        creator.add_intro_slide(data["structure"]["introduction"]["description"])
        # 4. 添加主题页和子主题页
        for topic in data["structure"]["topics"]["each_topic"]:
            # 添加主题页
            creator.add_topic_slide(topic["name"])

            # 添加子主题页
            for subtopic in topic["subtopics"]["each_subtopic"]:
                creator.add_subtopic_slide(subtopic)

        # 5. 添加总结页
        creator.add_conclusion_slide(data["structure"]["conclusion"]["sections"]["each_section"])

        # 保存PPT - 使用ppt_title作为文件名
        ppt_title = data["ppt_title"]["description"]
        # 移除Windows文件名中不允许的特殊字符
        safe_filename = re.sub(r'[\\/*?:"<>|]', "", ppt_title)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        output_filename = f"{safe_filename}_{timestamp}.pptx"
        
        download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(download_dir, exist_ok=True)  # 确保目录存在
        full_path = os.path.join(download_dir, output_filename)
        creator.save(full_path)
        #在用户目录下保存
        
        print(f"PPT生成完成，已保存为: {full_path}")
        self.pptgen_complete_signal.emit(full_path)