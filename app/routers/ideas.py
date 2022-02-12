from fastapi import APIRouter, Header
import mysql.connector
import threading
import hashlib

from app.config import *
from app import authentication as auth
from app.worker import DatabaseCleanupWorker
from app.models.user import *
from app.models.idea import IdeaPost
from app.models.token import AccessToken
from app.models.errors import *


router = APIRouter(
    prefix="/ideas",
    tags=["ideas"]
)

worker = None
worker_instance = DatabaseCleanupWorker()

db = mysql.connector.connect()


def is_db_up():
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    return True


# Event that set-ups the application for startup
@router.on_event("startup")
async def startup_event():
    global db
    db = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )
    # This makes it work without having to commit after every query
    db.autocommit = True
    # Create a worker
    # global worker
    # worker = threading.Thread(target=worker_instance.cleanup_database(), args=())


@router.get("/get")
async def get_ideas(page: Optional[int] = 0, cat: Optional[str] = None):
    # Worker to clean up database
    # global worker
    # global worker_instance
    # if worker_instance.worker_next_run == datetime(1970, 1, 1):
    #     print("First run for worker")
    #     worker.start()
    # elif worker.is_alive() is False and datetime.now() > worker_instance.worker_next_run:
    #     print("Worker has died and it is time to start again")
    #     worker = threading.Thread(target=worker_instance.cleanup_database(), args=())
    #     worker.start()
    # else:
    #    # print("No starting lol")

    is_db_up()
    cursor = db.cursor(dictionary=True)

    query = "SELECT " \
            "ideas.id, seller_id, title, short_desc, date_publish, date_expiry, price, " \
            "files.public_path AS image_url," \
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "WHERE buyer_id IS NULL AND " \
            "(%s IS NULL OR ideas.id IN (SELECT idea_id FROM ideas_categories WHERE category LIKE %s))" \
            "ORDER BY date_publish DESC LIMIT %s, %s "
    cursor.execute(
        query, (cat, cat, page * 10, (page + 1) * 10)
    )
    results = cursor.fetchall()

    # Check if there are results, don't waste time to continue if not
    if len(results) == 0:
        return {"countLeft": 0, "ideas": []}

    # Get categories in ia neat array
    for result in results:
        cursor.execute("SELECT category FROM ideas_categories WHERE idea_id=%s", (result["id"],))
        result["categories"] = list(map(lambda x: x["category"], cursor.fetchall()))

    # Find the number of ideas matching the criteria
    query = "SELECT COUNT(*) AS ideas_count " \
            "FROM ideas " \
            "WHERE ideas.buyer_id IS NULL AND " \
            "(%s IS NULL OR ideas.id IN (SELECT idea_id FROM ideas_categories WHERE category LIKE %s))"
    cursor.execute(query, (cat, cat))
    ideas_count = cursor.fetchone()["ideas_count"]

    # Calculate remaining ideas for endless scrolling feature
    if page == 0:
        ideas_left = ideas_count - len(results)
    else:
        ideas_left = ideas_count - (page * 10 + len(results))

    cursor.close()

    return {
        "countLeft": ideas_left,
        "ideas": results
    }


@router.get("/get/{idea_id}")
async def get_idea_by_id(idea_id: str, token: str = Header(None, convert_underscores=False)):
    access_token = auth.verify_access_token(token)
    # This checks if idea id is in the right format, i.e. MD5 hash
    if len(idea_id) != len(hashlib.md5().hexdigest()):
        raise IdeaIDInvalidError

    is_db_up()
    cursor = db.cursor(dictionary=True)
    query = "SELECT ideas.*, " \
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes, " \
            "files.public_path AS image_url " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "WHERE ideas.id = %s"
    cursor.execute(query, (idea_id,))
    result = cursor.fetchone()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "msg": "The idea was not found",
            "errno": 202
        })
    if result["buyer_id"] is not None and result["buyer_id"] is not access_token.user_id:
        raise IdeaAccessDeniedError
    # Fetch categories separately cos they are in different table
    cursor.execute("SELECT category FROM ideas_categories WHERE idea_id=%s", (result["id"],))
    result["categories"] = list(map(lambda x: x["category"], cursor.fetchall()))
    # Check if the user is the owner of the idea, then fetch the files
    if result["buyer_id"] != access_token.user_id:
        del result["long_desc"]
    else:
        cursor.execute("SELECT * FROM files WHERE idea_id=%s AND idea_id!=id", (result["id"],))
        result["files"] = list(cursor.fetchall())
    # print(result)
    cursor.close()

    return result


@router.get("/get-hottest")
def get_hottest_ideas():
    is_db_up()
    cursor = db.cursor(dictionary=True)
    query = "SELECT ideas.id, ideas.title, files.public_path AS image_url, " \
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "WHERE buyer_id IS NULL ORDER BY likes DESC LIMIT 5"
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    return results


@router.post("/post")
async def post_idea(idea: IdeaPost, token: str = Header(None, convert_underscores=False)):
    token_data: AccessToken = auth.verify_access_token(token)

    idea_id = hashlib.md5(idea.long_desc.encode()).hexdigest()
    is_db_up()
    cursor = db.cursor()
    query = "INSERT INTO ideas(id, seller_id, title, short_desc, long_desc, " \
            "date_publish, date_expiry, price) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)"
    data = (idea_id, token_data.user_id, idea.title, idea.short_desc, idea.long_desc, datetime.now().isoformat(),
            (datetime.now() + IDEA_EXPIRES_AFTER).isoformat(), idea.price)
    try:
        cursor.execute(query, data)
        for category in idea.categories:
            cursor.execute("INSERT INTO ideas_categories(idea_id, category) VALUES(%s, %s)", (idea_id, category))
    except mysql.errors.IntegrityError as ex:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)

    cursor.close()
    return idea_id


@router.put("/like")
async def like_idea(idea_id: str, token: str = Header(None, convert_underscores=False)):
    token_data = auth.verify_access_token(token)

    # This checks if idea id is in the right format, i.e. MD5 hash
    if len(idea_id) != len(hashlib.md5().hexdigest()):
        raise IdeaIDInvalidError

    is_db_up()
    cursor = db.cursor(dictionary=True)
    # Try to insert a like row in the table, if a duplication error is thrown, delete the like
    try:
        cursor.execute("INSERT INTO ideas_likes(idea_id, user_id) VALUES(%s, %s)", (idea_id, token_data.user_id))
    except mysql.connector.IntegrityError:
        cursor.execute("DELETE FROM ideas_likes WHERE idea_id = %s AND user_id = %s", (idea_id, token_data.user_id))
    # Get the number of likes
    query = "SELECT " \
            "COUNT(*) AS likes, " \
            "((SELECT COUNT(*) FROM ideas_likes WHERE idea_id=%s AND user_id=%s) = 1) AS is_liked " \
            "FROM ideas_likes WHERE idea_id = %s"
    cursor.execute(query, (idea_id, token_data.user_id, idea_id))
    likes = cursor.fetchone()
    cursor.close()
    if likes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "msg": "The idea was not found",
            "errno": 202
        })

    return likes


@router.on_event("shutdown")
async def shutdown_event():
    db.close()
