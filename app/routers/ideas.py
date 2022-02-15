from fastapi import APIRouter, Depends
import mysql.connector

from app.config import *
from app.dependencies import get_token_data
from app.functions import verify_idea_id, calculate_idea_id
from app.models.user import *
from app.models.idea import IdeaPost, IdeaPartial, IdeaFile, IdeaFull, IdeaSmall
from app.models.token import AccessToken
from app.models.errors import *
from app.responses.ideas import IdeasList, IdeasHottest, Like

router = APIRouter(
    prefix="/ideas",
    tags=["ideas"]
)

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


@router.get("/get", response_model=IdeasList)
async def get_ideas(page: Optional[int] = 0, cat: Optional[str] = None):
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
        return IdeasList(countLeft=0, ideas=list())

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

    return IdeasList(
        countLeft=ideas_left,
        ideas=list(map(lambda idea: IdeaPartial(
            id=idea["id"],
            sellerID=idea["seller_id"],
            title=idea["title"],
            likes=idea["likes"],
            imageURL=idea["image_url"],
            shortDesc=idea["short_desc"],
            datePublish=idea["date_publish"],
            dateExpiry=idea["date_expiry"],
            categories=idea["categories"],
            price=idea["price"]
        ), results))
    )


@router.get("/get/{idea_id}", response_model=IdeaFull)
async def get_idea_by_id(idea_id: str, token_data: AccessToken = Depends(get_token_data)):
    # This checks if idea id is in the right format, i.e. MD5 hash
    verify_idea_id(idea_id)
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
    if result["buyer_id"] is not None and result["buyer_id"] is not token_data.user_id:
        raise IdeaAccessDeniedError
    # Fetch categories separately cos they are in different table
    cursor.execute("SELECT category FROM ideas_categories WHERE idea_id=%s", (result["id"],))
    result["categories"] = list(map(lambda x: x["category"], cursor.fetchall()))
    # Check if the user is the owner of the idea, then fetch the files
    if result["buyer_id"] != token_data.user_id:
        del result["long_desc"]
    else:
        cursor.execute("SELECT * FROM files WHERE idea_id=%s AND idea_id!=id", (result["id"],))
        result["files"] = list(cursor.fetchall())
    cursor.close()

    return IdeaFull(
        id=result["id"],
        sellerID=result["seller_id"],
        buyerID=result["buyer_id"],
        title=result["title"],
        imageURL=result["image_url"],
        likes=result["likes"],
        shortDesc=result["short_desc"],
        longDesc=result["long_desc"] if 'long_desc' in result else None,
        files=list(map(lambda file: IdeaFile(
            id=file["id"],
            ideaID=file["idea_id"],
            name=file["name"],
            size=file["size"],
            absolutePath=file["absolute_path"],
            publicPath=file["public_path"],
            contentType=file["content_type"],
            uploadDate=file["upload_date"]
        ), result["files"])) if 'long_desc' in result else None,
        categories=result["categories"],
        price=result["price"],
        datePublish=result["date_publish"],
        dateExpiry=result["date_expiry"],
        dateBought=result["date_bought"]
    )


@router.get("/get-hottest", response_model=IdeasHottest)
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
    return IdeasHottest(
        ideas=list(map(lambda idea: IdeaSmall(
            id=idea["id"],
            title=idea["title"],
            imageURL=idea["image_url"],
            likes=idea["likes"]
        ), results))
    )


@router.post("/post")
async def post_idea(idea: IdeaPost, token_data: AccessToken = Depends(get_token_data)):
    idea_id = calculate_idea_id(idea.long_desc)
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
    except mysql.connector.errors.IntegrityError as ex:
        field = ex.msg.split()[5]
        if field == "'id'":
            raise IdeaDuplicationError
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)

    cursor.close()
    return idea_id


@router.put("/like", response_model=Like)
async def like_idea(idea_id: str, token_data: AccessToken = Depends(get_token_data)):
    # This checks if idea id is in the right format, i.e. MD5 hash
    verify_idea_id(idea_id)

    is_db_up()
    cursor = db.cursor(dictionary=True)
    # Try to insert a like row in the table, if a duplication error is thrown, delete the like
    try:
        cursor.execute("INSERT INTO ideas_likes(idea_id, user_id) VALUES(%s, %s)", (idea_id, token_data.user_id))
        is_liked = True
    except mysql.connector.IntegrityError:
        cursor.execute("DELETE FROM ideas_likes WHERE idea_id = %s AND user_id = %s", (idea_id, token_data.user_id))
        is_liked = False
    # Get the number of likes
    query = "SELECT " \
            "COUNT(*) AS likes_count, " \
            "((SELECT COUNT(*) FROM ideas_likes WHERE idea_id=%s AND user_id=%s) = 1) AS is_liked " \
            "FROM ideas_likes WHERE idea_id = %s"
    cursor.execute(query, (idea_id, token_data.user_id, idea_id))
    result = cursor.fetchone()
    cursor.close()
    if result is None:
        raise IdeaNotFoundError

    return Like(
        isLiked=is_liked,
        count=result["likes_count"]
    )


@router.on_event("shutdown")
async def shutdown_event():
    db.close()
