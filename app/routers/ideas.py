from fastapi import APIRouter, Depends
import asyncio
import aiomysql
from datetime import datetime
from typing import Optional

from app.config import DB_HOST, DB_USER, DB_PASS, DB_NAME, IDEA_EXPIRES_AFTER
from app.dependencies import get_token_data
from app.functions import verify_idea_id, calculate_idea_id
from app.models.idea import IdeaPost, IdeaPartial, IdeaFile, IdeaFull, IdeaSmall
from app.models.token import AccessToken
from app.errors.ideas import *
from app.responses.ideas import IdeasList, IdeasHottest, Like

router = APIRouter(
    prefix="/ideas",
    tags=["ideas"]
)

loop = asyncio.get_event_loop()


async def is_db_up():
    try:
        await db.ping(reconnect=True)
    except aiomysql.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    return True


# Event that set-ups the application for startup
@router.on_event("startup")
async def startup_event():
    # noinspection PyGlobalUndefined
    global db
    db = await aiomysql.connect(
        host=DB_HOST,
        port=3306,
        user=DB_USER,
        password=DB_PASS,
        db=DB_NAME,
        autocommit=True,
        loop=loop
    )
    # This makes it work without having to commit after every query
    db.autocommit = True


@router.get("/get", response_model=IdeasList)
async def get_ideas(page: Optional[int] = 0, cat: Optional[str] = None):
    await is_db_up()
    cursor = await db.cursor(aiomysql.DictCursor)
    query = "SELECT " \
            "ideas.id, seller_id, title, short_desc, date_publish, date_expiry, price, " \
            "files.public_path AS image_url," \
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "WHERE buyer_id IS NULL AND " \
            "(%s IS NULL OR ideas.id IN (SELECT idea_id FROM ideas_categories WHERE category LIKE %s))" \
            "ORDER BY date_publish DESC LIMIT %s, %s "
    await cursor.execute(query, (cat, cat, page * 10, (page + 1) * 10))
    results = await cursor.fetchall()
    # Check if there are results, don't waste time to continue if not
    if len(results) == 0:
        return IdeasList(countLeft=0, ideas=list())

    # Get categories
    for result in results:
        await cursor.execute("SELECT category FROM ideas_categories WHERE idea_id=%s", (result["id"],))
        result["categories"] = list(map(lambda x: x["category"], await cursor.fetchall()))

    # Find the number of ideas matching the criteria
    query = "SELECT COUNT(*) AS ideas_count " \
            "FROM ideas " \
            "WHERE ideas.buyer_id IS NULL AND " \
            "(%s IS NULL OR ideas.id IN (SELECT idea_id FROM ideas_categories WHERE category LIKE %s))"
    await cursor.execute(query, (cat, cat))
    ideas_count = await cursor.fetchone()
    # Calculate remaining ideas for endless scrolling feature
    if page == 0:
        ideas_left = ideas_count["ideas_count"] - len(results)
    else:
        ideas_left = ideas_count["ideas_count"] - (page * 10 + len(results))

    await cursor.close()

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
    verify_idea_id(idea_id)
    await is_db_up()

    cursor = await db.cursor(aiomysql.DictCursor)
    query = "SELECT ideas.*, " \
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes, " \
            "files.public_path AS image_url " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "WHERE ideas.id = %s"
    await cursor.execute(query, (idea_id,))
    result = await cursor.fetchone()

    if result is None:
        raise IdeaNotFoundError
    if result["buyer_id"] is not None and result["buyer_id"] is not token_data.user_id:
        raise IdeaAccessDeniedError

    # Get categories
    await cursor.execute("SELECT category FROM ideas_categories WHERE idea_id=%s", (result["id"],))
    result["categories"] = list(map(lambda x: x["category"], await cursor.fetchall()))

    # Check if the user is the owner of the idea, if so fetch the files, else remove long description
    if result["buyer_id"] != token_data.user_id:
        del result["long_desc"]
    else:
        await cursor.execute("SELECT * FROM files WHERE idea_id=%s AND idea_id!=id", (result["id"],))
        result["files"] = list(await cursor.fetchall())

    await cursor.close()

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
async def get_hottest_ideas():
    await is_db_up()

    cursor = await db.cursor(aiomysql.DictCursor)
    query = "SELECT ideas.id, ideas.title, files.public_path AS image_url, " \
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "WHERE buyer_id IS NULL ORDER BY likes DESC LIMIT 5"
    await cursor.execute(query)
    results = await cursor.fetchall()
    await cursor.close()

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
    await is_db_up()

    # Long description is used for id of the idea, because it needs to be unique
    idea_id = calculate_idea_id(idea.long_desc)

    cursor = await db.cursor(aiomysql.DictCursor)
    query = "INSERT INTO ideas(id, seller_id, title, short_desc, long_desc, " \
            "date_publish, date_expiry, price) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)"
    data = (idea_id, token_data.user_id, idea.title, idea.short_desc, idea.long_desc, datetime.now().isoformat(),
            (datetime.now() + IDEA_EXPIRES_AFTER).isoformat(), idea.price)
    try:
        await cursor.execute(query, data)
        for category in idea.categories:
            await cursor.execute("INSERT INTO ideas_categories(idea_id, category) VALUES(%s, %s)", (idea_id, category))
    except aiomysql.IntegrityError as ex:
        field = ex.msg.split()[5]
        if field == "'id'":
            raise IdeaDuplicationError
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)

    await cursor.close()

    return idea_id


@router.put("/like", response_model=Like)
async def like_idea(idea_id: str, token_data: AccessToken = Depends(get_token_data)):
    verify_idea_id(idea_id)
    await is_db_up()

    cursor = await db.cursor(aiomysql.DictCursor)
    # Try to insert a like row in the table, if a duplication error is thrown, delete the like
    try:
        await cursor.execute("INSERT INTO ideas_likes(idea_id, user_id) VALUES(%s, %s)", (idea_id, token_data.user_id))
        is_liked = True
    except aiomysql.IntegrityError:
        await cursor.execute(
            "DELETE FROM ideas_likes WHERE idea_id = %s AND user_id = %s",
            (idea_id, token_data.user_id)
        )
        is_liked = False

    # Get the number of likes
    query = "SELECT " \
            "COUNT(*) AS likes_count, " \
            "((SELECT COUNT(*) FROM ideas_likes WHERE idea_id=%s AND user_id=%s) = 1) AS is_liked " \
            "FROM ideas_likes WHERE idea_id = %s"
    await cursor.execute(query, (idea_id, token_data.user_id, idea_id))
    result = await cursor.fetchone()
    await cursor.close()

    if result is None:
        raise IdeaNotFoundError

    return Like(
        isLiked=is_liked,
        count=result["likes_count"]
    )


@router.on_event("shutdown")
async def shutdown_event():
    await db.close()
