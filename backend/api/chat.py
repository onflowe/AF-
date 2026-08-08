import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.models.model import ChatRequest,ChatResponse
from backend.core.agent.RectAgent import RectAgentService


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000", "http://127.0.0.1:5000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def get_index():
    return FileResponse("frontend/index.html")

@app.post("/api/chat/record")
def chat(request: ChatRequest)->ChatResponse:
    agent = RectAgentService()
    uid = request.user_id
    sid = request.session_id

    full_response = ''
    for chunk in agent.execute_stream(uid,sid, request.Human_content):
        full_response += chunk


    return ChatResponse(response=full_response)





if __name__ == "__main__":

    uvicorn.run(app, host="127.0.0.1", port=8000)
    #cd backend
    #uvicorn backend.api.chat:app --reload