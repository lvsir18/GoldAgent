"""Run the GoldAgent API."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8080, reload=False)
