from fastapi import APIRouter
import redis

from app.database import database
from app.config import REDIS_PASS
from app.internal.responses.ideas import Idea, Category, IdeasList
from app.cache import invalidate_ideas

router = APIRouter(
    prefix="/ideas",
)


@router.get("", response_model=IdeasList)
async def get_ideas():
    ideas = await database.fetch_all(
        query="SELECT ideas.id, seller_id, buyer_id, title, short_desc, date_publish, date_expiry, date_bought, price, "
              "(SELECT COUNT(*) FROM ideas_likes WHERE ideas_likes.idea_id = ideas.id) AS likes ,"
              "(SELECT public_path FROM files WHERE files.id = ideas.id) AS image_url "
              "FROM ideas ORDER BY date_publish DESC"
    )
    # Convert list of sqlalchemy rows to dict, so it is possible to add new keys
    ideas = list(map(lambda item: dict(item), ideas))

    for idea in ideas:
        idea["categories"] = await database.fetch_all(
            query="SELECT category FROM ideas_categories WHERE idea_id = :idea_id",
            values={"idea_id": idea["id"]}
        )

    return IdeasList(
        ideas=list(map(lambda temp: Idea(
            id=temp["id"],
            sellerID=temp["seller_id"],
            buyerID=temp["buyer_id"],
            title=temp["title"],
            shortDesc=temp["short_desc"][:35] + "...",
            datePublish=temp["date_publish"],
            dateExpiry=temp["date_expiry"],
            dateBought=temp["date_bought"],
            price=temp["price"],
            likes=temp["likes"],
            imageURL=temp["image_url"],
            categories=list(map(lambda category: Category(
                category=category["category"]
            ), temp["categories"]))
        ), ideas))
    )


@router.delete("/{idea_id}")
async def delete_idea(idea_id: str):
    # Delete cache when deleting an idea
    invalidate_ideas()

    # Delete all idea entries
    await database.execute(
        query="DELETE FROM ideas WHERE id = :idea_id",
        values={"idea_id": idea_id}
    )
    await database.execute(
        query="DELETE FROM ideas_categories WHERE idea_id = :idea_id",
        values={"idea_id": idea_id}
    )
    await database.execute(
        query="DELETE FROM ideas_likes WHERE idea_id = :idea_id",
        values={"idea_id": idea_id}
    )
    await database.execute(
        query="DELETE FROM payments WHERE idea_id = :idea_id",
        values={"idea_id": idea_id}
    )
    await database.execute(
        query="DELETE FROM payouts WHERE idea_id = :idea_id",
        values={"idea_id": idea_id}
    )
    await database.execute(
        query="DELETE FROM files WHERE idea_id = :idea_id",
        values={"idea_id": idea_id}
    )
    return {"status": "success"}
