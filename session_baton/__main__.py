import uvicorn

from session_baton.server import HOST, PORT

uvicorn.run("session_baton.server:app", host=HOST, port=int(PORT))
