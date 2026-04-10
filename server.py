from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import anthropic
import json
import os

app = FastAPI()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

AGENT_ID = "agent_011CZvfMer4ZdyYnsp31rxWp"
ENV_ID = "env_01ErGb1bXWJUCF7M8ZhPXfJk"
VAULT_ID = "vlt_011CZvXnxwWY2NG8ZdoojQAQ"
BETAS = ["managed-agents-2026-04-01"]

# Almacén de sesiones en memoria
sessions = {}


class ChatRequest(BaseModel):
    user_id: str
    message: str


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if req.user_id not in sessions:
        session = client.beta.sessions.create(
            agent=AGENT_ID,
            environment_id=ENV_ID,
            vault_ids=[VAULT_ID],
            betas=BETAS,
        )
        sessions[req.user_id] = session.id

    session_id = sessions[req.user_id]

    client.beta.sessions.events.send(
        session_id=session_id,
        events=[{
            "type": "user.message",
            "content": [{"type": "text", "text": req.message}],
        }],
        betas=BETAS,
    )

    def generate():
        for event in client.beta.sessions.events.stream(
            session_id=session_id, betas=BETAS
        ):
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        yield f"data: {json.dumps({'text': block.text})}\n\n"
            elif event.type == "session.status_idle":
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

    return StreamingResponse(generate(), media_type="text/event-stream")


app.mount("/", StaticFiles(directory="static", html=True), name="static")