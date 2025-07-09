import os
import contextlib
from fastapi import FastAPI
from servers import youtube_server  # your MCP module

PORT = int(os.environ.get("PORT", 8000))

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(youtube_server.session_manager.run())
        yield

app = FastAPI(lifespan=lifespan)

# Mount the MCP server
app.mount("/youtube", youtube_server.streamable_http_app())

@app.get("/")
def root():
    return {"status": "YouTube MCP server is running"}
