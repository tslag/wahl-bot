from contextlib import asynccontextmanager

import uvicorn
from api.routes.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.programs import router as programs_router
from api.routes.tasks import router as tasks_router
from core.logging import logger
from db.session import engine, initialize_database
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code that runs on startup
    logger.info("Starting up")

    # Wait for database to be ready
    import asyncio

    max_retries = 5
    for attempt in range(max_retries):
        try:
            logger.info("Initializing database tables if not exist")
            await initialize_database()
            logger.info("Database tables created successfully")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(
                    "Database connection attempt %d failed: %s. Retrying..",
                    attempt + 1,
                    e,
                )
                await asyncio.sleep(2)
            else:
                logger.exception(
                    "Failed to create database tables after %d attempts", max_retries
                )
                raise

    yield
    # Code that runs on shutdown
    logger.info("Shutting down")
    await engine.dispose()


app = FastAPI(lifespan=lifespan, root_path="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],  # Vite default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """
    Description
    -----------
        Landingpage
    """
    return JSONResponse({"message": "Wahlbot Backend"})


app.include_router(auth_router)
app.include_router(programs_router)
app.include_router(chat_router)
app.include_router(tasks_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
