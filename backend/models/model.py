from pydantic import  BaseModel

#请求体
class ChatRequest(BaseModel):
    Human_content: str
    session_id: str  #默认为s001

#响应体
class ChatResponse(BaseModel):
    response: str