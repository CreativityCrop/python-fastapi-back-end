import redis

from app.config import REDIS_PASS


def invalidate_ideas():
    r = redis.Redis(host='localhost', password=REDIS_PASS, port=6379, db=0)
    r.flushall()
    # r.delete("cc-cache:app.routers.ideas.get_ideas*")
    r.close()
