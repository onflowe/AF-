from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage,SystemMessage

from backend.models.model_factory import chat_model
from backend.core.rag.memory import memory_service
from backend.utils.prompt_handle import load_system_prompt
from backend.core.agent.tools import create_tool


class RectAgentService:
    def __init__(self):
        
        self.model= chat_model
        self.system_prompt=load_system_prompt()
       

        

    


    #流式输出
    # 在你的 RectAgentService 类中
    def execute_stream(self,user_id,session_id :str, request: str):
        full_response = ""
        full_msg = None
        history_message = memory_service.get_history_str(user_id,session_id)["full_context"]

        # ... 构建 messages 的代码 ...
        input_dict = {
            "messages" :[SystemMessage(history_message)] +[HumanMessage(request)],

        }
        tools = create_tool(user_id,session_id)
        #分块传出，查看元块数据，测试用
        agent = create_agent(
                    model=self.model,
                    system_prompt=self.system_prompt,
                    tools=[tools]
        
                )

        for chunk in agent.stream(input_dict, stream_mode="messages"): #values :<class 'dict'> 全部信息 chunk1 :{"messages" : [HumanMessage(..),AIMessage(..)]
                                                                            #messages : <class 'tuple'>   chunk1 : (AIMessage(..),{metadata})
            # isinstance( 判断对象 ，类型 )   判断 对象 是否为该 类型
            if isinstance(chunk,tuple):
                msg,metadata = chunk           #拿到AIMessage-----msg
                if isinstance(msg,AIMessage):
                    full_msg = msg
                    if msg.content:
                        full_response += msg.content
                        yield msg.content    # “messages” 模式下 AIMessage 中的 content 是流式存储的的
        if full_msg and full_response:
            memory_service.add_message(user_id,session_id,request,full_response )





if __name__ == '__main__':
    agent = RectAgentService()
    full_response = ''
    for chunk in agent.execute_stream("u001","s001","你是什么大模型"):
       full_response += chunk
    print(full_response)


