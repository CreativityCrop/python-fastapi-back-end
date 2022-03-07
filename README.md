# CreativityCrop FastAPI Back End

This is the back end (API) for the CreativityCrop project. Created with FastAPI and served by uvicorn and proxied by nginx.

## Prerequisites

This python project requires the following pieces of software:
* python 3.9
* docker (only for deployment)
* MySQL compatible database with a table from the provided `schema.sql`

## Installation

Clone the project or download an archive.

```bash
git clone https://github.com/CreativityCrop/react-front-end.git
```

Create a virtual environment for the python project and activate it

```bash
python -m venv && source venv/bin/activate
```

Then install all the required dependencies

```bash
pip install -r requirements.txt
```

## Usage

```bash
# runs in development environment
python main.py

# for production, you need to run docker and build a container
docker build -t creativitycrop-api ./

# then run the container
docker run -p 8000:8000 creativitycrop-api

# executes automated tests
pytest
```

## Configuration

You need to create a `config.py` file in `app/` directory. You should use the provided `config.py.example` file and just fill it.

## Deployment

The built container can be run on any machine with docker.

For the proper operation of the whole platform a database cleaning worker is required. It consists of a simple file that should be run in regular periods by a cron job. You can use the following example code

Execute this command to edit your cron file `crontab -e`, and append this line at the end 

`*/5 * * * * cd /home/ubuntu/python-fastapi-back-end && source venv/bin/activate && python app/worker.py && deactivate`


## License

[GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.html)