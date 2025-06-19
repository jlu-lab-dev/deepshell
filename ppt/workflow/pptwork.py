from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain.schema.runnable import (
    ConfigurableField,
    Runnable,
    RunnableLambda,
    RunnableMap,
    RunnablePassthrough,
)
from langchain.schema.messages import AIMessage, HumanMessage, BaseMessage
from config.config_manager import ConfigManager
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from operator import itemgetter
from ppt.prompts.simplePrompt import SIMPLE_PROMPT
from ppt.prompts.ragPrompt import RAG_GEN_PPT_PROMPT, RAG_ANALYSIS_PROMPT, REPHRASE_TEMPLATE
from ppt.prompts.mutiPrompt import GEN_PPT_PROMPT,ANALYSIS_PROMPT
import re
import json
class PPTwork:
    def __init__(self, config ,is_online=True):
        self.llm = ChatOpenAI(
            model=config["model_name"],
            api_key=config["api_key"],
            base_url=config["api_base"],
            max_tokens=config["max_tokens"],
            temperature=config["temperature"],
        )
        pass


    def format_docs(self,docs):
        return "\n\n".join(doc.page_content for doc in docs)
    # 传统方式召回，单问题召回，然后llm总结答案回答
    def simple_chain(self,input_requirement):
        simple_prompt = PromptTemplate.from_template(SIMPLE_PROMPT)

        _chain = (
            {"requirement":RunnablePassthrough()}
            |simple_prompt
            |self.llm
            |StrOutputParser()
        )
        return _chain.stream({"requirement":input_requirement})

    # def rag_chain(self,message):
    #     ana_prompt = PromptTemplate.from_template(RAG_ANALYSIS_PROMPT)
    #     gen_prompt = PromptTemplate.from_template(RAG_GEN_PPT_PROMPT)
    #     # rephase_prompt = PromptTemplate.from_template(REPHRASE_TEMPLATE)
    #
    #     _analysis = (
    #         {
    #             "requirement":RunnableLambda(itemgetter("requirement")),
    #             "history":RunnableLambda(itemgetter("history"))| self.serialize_history,
    #             "context":RunnablePassthrough()
    #         }|ana_prompt
    #         |self.llm
    #         |StrOutputParser()
    #         |(lambda res: self.safe_json_parse(res))
    #     )
    #     _gen = (
    #         {
    #             "title": RunnableLambda(itemgetter("title")),
    #             "outline": RunnableLambda(itemgetter("outline")),
    #             "keywords": RunnableLambda(itemgetter("keywords")),
    #             "context":RunnablePassthrough(),
    #             "history":RunnableLambda(itemgetter("history"))| self.serialize_history,
    #         }|gen_prompt
    #         |self.llm
    #         |StrOutputParser()
    #     )
    #     _chain = (
    #         _analysis
    #         | (lambda res: {
    #             "title": res.get("title", ""),
    #             "outline": res.get("outline", ""),
    #             "keywords": res.get("keywords", ""), # 将keywords作为context传递给_gen
    #             "history":message["history"]
    #         })
    #         | _gen
    #     )
    #     return _chain.stream(message)

    # 用大模型判断用户的想法：“大纲”或“内容”。根据本次需求，和上一次的一问一答的对话
    def judge_user_intention(self, user_requirement, history):
        # 判断历史记录长度是否大于等于2
        if len(history) >= 2:
            # 若大于等于2，取最后两条记录
            last_two_history = history[-2:]
        else:
            # 若小于2，取全部历史记录
            last_two_history = history

        serialized_history = self.serialize_history(last_two_history)
        intention_prompt = PromptTemplate.from_template("""
           判断用户的需求是更偏向于生成ppt大纲还是生成ppt内容，参考历史对话记录。
           请仅回答“ppt大纲”或“ppt内容”。
           历史对话记录: {serialized_history}
           用户需求: {user_requirement}
           """)
        _chain = (
            {
                "user_requirement": RunnableLambda(lambda x: x["user_requirement"]),
                "serialized_history": RunnableLambda(lambda x: x["serialized_history"])
            }
            | intention_prompt
            | self.llm
            | StrOutputParser()
        )
        result = _chain.invoke({
            "user_requirement": user_requirement,
            "serialized_history": serialized_history
        })
        return result


    def rag_chain(self, message):
        requirement = message["requirement"]

        if "ppt大纲" in requirement:
            ana_prompt = PromptTemplate.from_template(RAG_ANALYSIS_PROMPT)
            _analysis = (
                    {
                        "title": RunnableLambda(itemgetter("title")),
                        "outline": RunnableLambda(itemgetter("outline")),
                        "keywords": RunnableLambda(itemgetter("keywords")),
                        "requirement": RunnableLambda(itemgetter("requirement")),    # 从message中提取requirement字段。
                        "history": RunnableLambda(itemgetter("history")) | self.serialize_history,
                        "context": RunnablePassthrough()
                    }
                    | ana_prompt
                    | self.llm
                    | StrOutputParser()
                    # | (lambda res: self.safe_json_parse(res))
            )
            # result = _analysis.invoke(message)
            # message["title"] = result.get("title", "")  # 保存标题
            # message["outline"] = result.get("outline", "")  # 保存大纲
            # message["keywords"] = result.get("keywords", "")  # 保存关键词
            # return _analysis.stream(message)
            result = _analysis.invoke(message)
            try:
                parsed_result = self.safe_json_parse(result)
                message["title"] = parsed_result.get("title", "")
                message["outline"] = parsed_result.get("outline", "")
                message["keywords"] = parsed_result.get("keywords", "")
            except ValueError:
                print("解析结果为JSON时出错，可能结果不是有效的JSON格式。")
            return result

        elif "ppt内容" in requirement:
            gen_prompt = PromptTemplate.from_template(RAG_GEN_PPT_PROMPT)
            _gen = (
                    {
                        "requirement": RunnableLambda(itemgetter("requirement")),
                        "title": RunnableLambda(itemgetter("title")),
                        "outline": RunnableLambda(itemgetter("outline")),
                        "keywords": RunnableLambda(itemgetter("keywords")),
                        "context": RunnablePassthrough(),
                        "history": RunnableLambda(itemgetter("history")) | self.serialize_history,
                    }
                    | gen_prompt
                    | self.llm
                    | StrOutputParser()
            )
            return _gen.stream(message)

    # 多问题召回，每次召回后，问题和答案同时作为下一次召回的参考
    def muti_chain(self, input_requirement):
        ana_prompt = PromptTemplate.from_template(ANALYSIS_PROMPT)
        gen_prompt = PromptTemplate.from_template(GEN_PPT_PROMPT)
        _analysis = (
            {"requirement":RunnablePassthrough()}
            |ana_prompt
            |self.llm
            |StrOutputParser()
            |(lambda res: self.safe_json_parse(res))
        )
        _gen = (
            {
                "title": RunnableLambda(itemgetter("title")),
                "outline": RunnableLambda(itemgetter("outline")),
                "keywords": RunnableLambda(itemgetter("keywords")),
            }|gen_prompt
            |self.llm
            |StrOutputParser()
        )
        _chain = (
            _analysis
            | (lambda res: {
                "title": res.get("title", ""),
                "outline": res.get("outline", ""),
                "keywords": res.get("keywords", "")  # 将keywords作为context传递给_gen
            })
            | _gen
        )
        return _chain.stream({"requirement":input_requirement})

    def serialize_history(self, history):
        converted_history = []
        for message in history:
            if message[0] == "user":
                converted_history.append(HumanMessage(content=message[1]))
            elif message[0] == "sys":
                converted_history.append(AIMessage(content=message[1]))
        return converted_history

    def safe_json_parse(self,response):
        JSON_REGEX = re.compile(r'```json\s*([\s\S]*?)\s*```')
        try:
            # 尝试提取被代码块包裹的JSON
            match = JSON_REGEX.search(response)
            if match:
                return json.loads(match.group(1).strip())
            # 尝试直接解析整个响应
            return json.loads(response.strip())
        except Exception as e:
            print(f"JSON解析异常: {str(e)}")  # 保留错误日志
            return None




if __name__ == "__main__":
    config_manager = ConfigManager()
    # test get config
    config = config_manager.get_model_config('Qwen-PLUS')
    llm_model = ChatOpenAI(
                model=config["model_name"],
                api_key=config["api_key"],
                base_url=config["api_base"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
    )



