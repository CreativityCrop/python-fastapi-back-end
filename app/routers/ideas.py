from fastapi import APIRouter, Depends, Form, UploadFile, File
from datetime import datetime
from typing import Optional, List
from fastapi_redis_cache import FastApiRedisCache, cache, cache_one_hour

from app.config import DB_HOST, DB_USER, DB_PASS, DB_NAME, IDEA_EXPIRES_AFTER
from app.database import database
from app.dependencies import get_token_data
from app.functions import verify_idea_id, calculate_idea_id, save_file
from app.models.idea import IdeaPost, IdeaPartial, IdeaFile, IdeaFull, IdeaSmall
from app.models.token import AccessToken
from app.errors.ideas import *
from asyncmy.errors import IntegrityError
from app.responses.ideas import IdeasList, IdeasHottest, Like

router = APIRouter(
    prefix="/ideas",
    tags=["ideas"]
)


@router.get("/get", response_model=IdeasList)
@cache(expire=180)
async def get_ideas(page: Optional[int] = 0, cat: Optional[str] = None):
    query = "SELECT " \
            "ideas.id, seller_id, title, short_desc, date_publish, date_expiry, price, " \
            "files.public_path AS image_url," \
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "WHERE buyer_id IS NULL AND " \
            "(:cat IS NULL OR ideas.id IN (SELECT idea_id FROM ideas_categories WHERE category LIKE :cat))" \
            "ORDER BY date_publish DESC LIMIT :start, :end"
    results = await database.fetch_all(
        query=query,
        values={
            "cat": cat,
            "start": page * 10,
            "end": ((page + 1) * 10)
        }
    )

    # Convert list of sqlalchemy rows to dict, so it is possible to add new keys
    results = list(map(lambda item: dict(item), results))

    # Check if there are results, don't waste time to continue if not
    if len(results) == 0:
        return IdeasList(countLeft=0, ideas=list())

    # Get categories
    for result in results:
        categories = await database.fetch_all(
            query="SELECT category FROM ideas_categories WHERE idea_id=:idea_id",
            values={"idea_id": result["id"]}
        )
        result["categories"] = list(map(lambda x: x["category"], categories))

    # Find the number of ideas matching the criteria
    query = "SELECT COUNT(*) AS ideas_count " \
            "FROM ideas " \
            "WHERE ideas.buyer_id IS NULL AND " \
            "(:cat IS NULL OR ideas.id IN (SELECT idea_id FROM ideas_categories WHERE category LIKE :cat))"
    ideas_count = await database.fetch_val(query=query, values={"cat": cat}, column="ideas_count")

    # Calculate remaining ideas for endless scrolling feature
    if page == 0:
        ideas_left = ideas_count - len(results)
    else:
        ideas_left = ideas_count - (page * 10 + len(results))

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
    ).dict()


@router.get("/get/{idea_id}", response_model=IdeaFull)
@cache_one_hour()
async def get_idea_by_id(idea_id: str, token_data: AccessToken = Depends(get_token_data)):
    verify_idea_id(idea_id)

    query = "SELECT ideas.*, " \
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes, " \
            "files.public_path AS image_url, " \
            "payments.status AS payment_status, payments.user_id AS payment_user " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "LEFT JOIN payments ON ideas.id = payments.idea_id " \
            "WHERE ideas.id = :idea_id"
    # Fetch result and convert it to dict, so values can be changed
    result = dict(await database.fetch_one(query=query, values={"idea_id": idea_id}))

    if result is None:
        raise IdeaNotFoundError
    if result["buyer_id"] is not None and result["buyer_id"] is not token_data.user_id:
        if result["payment_user"] is token_data.user_id and result["payment_status"] == "requires_payment_method":
            pass
        else:
            raise IdeaAccessDeniedError

    # Get categories
    result["categories"] = list(map(lambda x: x["category"], await database.fetch_all(
        query="SELECT category FROM ideas_categories WHERE idea_id=:idea_id", values={"idea_id": result["id"]}
    )))

    # Check if the user is the owner of the idea, if so fetch the files, else remove long description
    if result["buyer_id"] != token_data.user_id:
        del result["long_desc"]
    else:
        result["files"] = await database.fetch_all(
            query="SELECT * FROM files WHERE idea_id=:idea_id AND idea_id!=id", values={"idea_id": result["id"]}
        )

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
        # categories=result["categories"],
        price=result["price"],
        datePublish=result["date_publish"],
        dateExpiry=result["date_expiry"],
        dateBought=result["date_bought"]
    ).dict()


@router.get("/get-hottest", response_model=IdeasHottest)
@cache(expire=600)
async def get_hottest_ideas():
    query = "SELECT ideas.id, ideas.title, files.public_path AS image_url, " \
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "WHERE buyer_id IS NULL ORDER BY likes DESC LIMIT 5"
    results = await database.fetch_all(query)

    return IdeasHottest(
        ideas=list(map(lambda idea: IdeaSmall(
            id=idea["id"],
            title=idea["title"],
            imageURL=idea["image_url"],
            likes=idea["likes"]
        ), results))
    ).dict()


@router.post("/post")
async def post_idea(idea: IdeaPost, token_data: AccessToken = Depends(get_token_data)):
    # Long description is used for id of the idea, because it must be unique
    idea_id = calculate_idea_id(idea.long_desc)

    query = "INSERT INTO ideas(id, seller_id, title, short_desc, long_desc, date_publish, date_expiry, price) " \
            "VALUES(:idea_id, :seller_id, :title, :short_desc, :long_desc, :date_publish, :date_expiry, :price)"
    data = {
        "idea_id": idea_id,
        "seller_id": token_data.user_id,
        "title": idea.title,
        "short_desc": idea.short_desc,
        "long_desc": idea.long_desc,
        "date_publish": datetime.now().isoformat(),
        "date_expiry": (datetime.now() + IDEA_EXPIRES_AFTER).isoformat(),
        "price": idea.price
    }
    try:
        await database.execute(query=query, values=data)
        if idea.categories is not None:
            for category in idea.categories:
                await database.execute(
                    query="INSERT INTO ideas_categories(idea_id, category) VALUES(:idea_id, :category)",
                    values={"idea_id": idea_id, "category": category}
                )
    except IntegrityError as ex:
        field = ex.args[1].split()[5]
        if field == "'id'":
            raise IdeaDuplicationError
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)
    return idea_id


@router.post("/post2")
async def post_idea_dos(
        files: List[UploadFile] = File(None),
        title: str = Form(...),
        image: UploadFile = File(...),
        short_desc: str = Form(...),
        long_desc: str = Form(...),
        categories: str = Form(None),
        price: float = Form(...),
        token_data: AccessToken = Depends(get_token_data),
):
    # Long description is used for id of the idea, because it must be unique
    idea_id = calculate_idea_id(long_desc)
    # Multipart handles arrays as string seperated by commas, so split is needed
    categories = categories.split(",") if categories is not None else None

    query = "INSERT INTO ideas(id, seller_id, title, short_desc, long_desc, date_publish, date_expiry, price) " \
            "VALUES(:idea_id, :seller_id, :title, :short_desc, :long_desc, :date_publish, :date_expiry, :price)"
    data = {
        "idea_id": idea_id,
        "seller_id": token_data.user_id,
        "title": title,
        "short_desc": short_desc,
        "long_desc": long_desc,
        "date_publish": datetime.now().isoformat(),
        "date_expiry": (datetime.now() + IDEA_EXPIRES_AFTER).isoformat(),
        "price": price
    }
    try:
        await database.execute(query=query, values=data)
        if categories is not None:
            for category in categories:
                await database.execute(
                    query="INSERT INTO ideas_categories(idea_id, category) VALUES(:idea_id, :category)",
                    values={"idea_id": idea_id, "category": category}
                )
    except IntegrityError as ex:
        field = ex.args[1].split()[5]
        if field == "'id'":
            raise IdeaDuplicationError
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)

    # Saving title image
    await save_file(file=image, kind="idea-title", uid=idea_id)

    # Saving each file
    if files is not None:
        for file in files:
            await save_file(file=file, kind="idea-file", uid=idea_id)

    return idea_id


@router.put("/like", response_model=Like)
async def like_idea(idea_id: str, token_data: AccessToken = Depends(get_token_data)):
    verify_idea_id(idea_id)

    buyer_id = await database.fetch_val(
        query="SELECT buyer_id FROM ideas WHERE id=:idea_id", values={"idea_id": idea_id}, column="buyer_id"
    )
    if buyer_id is not None:
        raise IdeaLikeDenied

    # Try to insert a like row in the table, if a duplication error is thrown, delete the like
    try:
        await database.execute(
            query="INSERT INTO ideas_likes(idea_id, user_id) VALUES(:idea_id, :user_id)",
            values={"idea_id": idea_id, "user_id": token_data.user_id}
        )
        is_liked = True
    except IntegrityError:
        await database.execute(
            query="DELETE FROM ideas_likes WHERE idea_id = :idea_id AND user_id = :user_id",
            values={"idea_id": idea_id, "user_id": token_data.user_id}
        )
        is_liked = False

    # Get the number of likes
    query = "SELECT " \
            "COUNT(*) AS likes_count, " \
            "((SELECT COUNT(*) FROM ideas_likes WHERE idea_id=:idea_id AND user_id=:user_id) = 1) AS is_liked " \
            "FROM ideas_likes WHERE idea_id = :idea_id"
    result = await database.fetch_one(query=query, values={"idea_id": idea_id, "user_id": token_data.user_id})

    if result is None:
        raise IdeaNotFoundError

    return Like(
        isLiked=is_liked,
        count=result["likes_count"]
    )
