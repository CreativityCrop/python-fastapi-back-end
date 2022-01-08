import uvicorn
from uvicorn.config import LOGGING_CONFIG


if __name__ == "__main__":
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s %(levelprefix)s %(message)s"
    LOGGING_CONFIG["formatters"]["access"][
        "fmt"] = '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'

    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=True)
