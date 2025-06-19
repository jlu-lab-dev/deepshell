from xmind.core.workbook import WorkbookDocument
from xmind.core.topic import TopicElement
import xmind
import re
from typing import Dict, List, Optional
import os

def log_message(message: str) -> None:
    """日志记录函数"""
    print(f"[INFO] {message}")


def handle_exception(message: str) -> None:
    """异常处理函数"""
    print(f"[ERROR] {message}")


class MindMapNode:
    """思维导图节点数据结构"""
    def __init__(self, title: str, depth: int):
        self.title = title.strip()
        self.depth = depth
        self.children: List[MindMapNode] = []



class MindMapWork:
    def __init__(self):
        pass
    def parse_outline(self, text: str) -> Optional[MindMapNode]:
        """解析大模型生成的层级文本，存入MindMapNode结构"""
        # 预处理：过滤空行并保留原始缩进
        lines = [line.rstrip() for line in text.split('\n') if line.strip()]
        if not lines:
            return None

        # 动态创建根节点
        root = None
        stack = []

        for line in lines:
            if not line.strip().startswith('-'):
                continue

            # 计算缩进深度（支持4空格/tab混用）
            indent = len(re.match(r'^[\s\t]*', line).group())
            if '\t' in line[:indent]:  # 处理tab缩进
                depth = line[:indent].count('\t')
            else:  # 空格缩进（4空格为一级）
                depth = indent // 4
            # 提取标题内容
            title = re.sub(r'^[-\s\t]+', '', line).strip()
            if not title:
                continue
            # 创建节点
            node = MindMapNode(title, depth)
            # 设置根节点（第一个有效节点）
            if not root:
                root = node
                stack = [root]
                continue

            # 寻找父节点（处理异常缩进）
            while stack and stack[-1].depth >= depth:
                stack.pop()
            if not stack:  # 兜底处理
                stack.append(root)

            # 挂载节点
            stack[-1].children.append(node)
            stack.append(node)

        return root or MindMapNode("空白主题", 0)

    def build_xmind(self, root: MindMapNode, filename: str) -> bool:
        """创建XMind文件"""
        try:
            # 创建新的XMind工作簿
            wb = WorkbookDocument()
            sheet = wb.getPrimarySheet()
            sheet.setTitle("思维导图")

            # 设置根主题
            root_topic = sheet.getRootTopic()
            root_topic.setTitle(root.title)

            def add_children(parent: TopicElement, nodes: List[MindMapNode]) -> None:
                """递归添加子节点"""
                for node in nodes:
                    child = parent.addSubTopic()
                    child.setTitle(node.title)
                    print(node.title)
                    add_children(child, node.children)

            # 构建子节点
            add_children(root_topic, root.children)
            download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            os.makedirs(download_dir, exist_ok=True)  # 确保目录存在
            full_path = os.path.join(download_dir, filename)
            #在用户目录下保存
            
            # 保存文件
            if not full_path.endswith('.xmind'):
                full_path += '.xmind'
            xmind.save(workbook=wb, path=full_path)
            return full_path
        except Exception as e:
            handle_exception(f"XMind生成失败: {str(e)}")
            return None


    # def generation_chain(self):
    #     """构建处理链式"""
    #     return (
    #             RunnablePassthrough()
    #             | self.MINDMAP_PROMPT
    #             | self.llm
    #             | RunnableLambda(lambda x: x.content)
    #             | RunnableLambda(self.parse_outline) #生成树形结构
    #     )

def print_mindmap(node: MindMapNode, indent=0) -> None:
    """可视化打印节点树结构"""
    if not node:
        print("Empty MindMap")
        return

    prefix = "    " * indent
    print(f"{prefix}└── {node.title} (depth:{node.depth})")
    for child in node.children:
        print_mindmap(child, indent + 1)


# if __name__ == "__main__":
    # # 配置加载
    # config_manager = ConfigManager()
    # config = config_manager.get_model_config('Qwen-PLUS')

    # # 初始化工作流
    # mindmap_work = MindMapWork(config)

    # # 执行生成链
    # chain = mindmap_work.generation_chain()
    # result = chain.invoke("请生成关于高中物理知识的思维导图")
    # print(result)
    # print_mindmap(result)

    # # 输出XMind文件
    # if result:
    #     success = mindmap_work.build_xmind(result, "test.xmind")
    #     if success:
    #         print("思维导图生成成功！")
    #     else:
    #         print("文件保存失败")