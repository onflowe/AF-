import uvicorn
from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.models.model import ChatRequest,ChatResponse
from backend.core.agent.RectAgent import RectAgentService


app = FastAPI()


@app.get("/")
def get_index():
    return FileResponse("frontend/index.html")

@app.post("/api/chat/record")
def chat(request: ChatRequest)->ChatResponse:
    agent = RectAgentService()

    full_response = ''
    for chunk in agent.execute_stream(request.session_id, request.Human_content):
        full_response += chunk


    return ChatResponse(response=full_response)

# 如果你想把静态文件放在 frontend/static 目录下
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")



if __name__ == "__main__":

    uvicorn.run(app, host="127.0.0.1", port=8000)
    #uvicorn backend.api.chat:app --reload