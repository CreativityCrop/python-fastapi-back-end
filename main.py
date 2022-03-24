import logging

import uvicorn
from uvicorn.config import LOGGING_CONFIG


if __name__ == "__main__":
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s %(levelprefix)s %(message)s"
    LOGGING_CONFIG["formatters"]["access"][
        "fmt"] = '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
    # LOGGING_CONFIG["handlers"]["file"]["filename"] = "uvicorn.log"

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        # For development purposes uncomment next line
        reload=True,
        root_path="/api",
        workers=8
    )
