from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException
from starlette import status
import mysql.connector
import stripe
import aiofiles as aiofiles
import hashlib

import app.authentication as auth
from app.config import *
from app.dependencies import get_token_data
from app.errors.account import InvoiceUnavailableYetError, InvoiceAccessUnauthorizedError
from app.errors.files import FiletypeNotAllowedError
from app.errors.ideas import IdeaNotFoundError
from app.functions import verify_idea_id
from app.models.idea import IdeaFile
from app.models.token import AccessToken
from app.responses.account import *

router = APIRouter(
    prefix="/account",
    tags=["account"]
)

stripe.api_key = str(STRIPE_API_KEY)

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


@router.get("", response_model=AccountData)
async def get_account(token_data: AccessToken = Depends(get_token_data)):
    is_db_up()
    cursor = db.cursor(dictionary=True)
    query = "SELECT users.*, " \
            "files.public_path AS avatar_url, " \
            "payments.id AS unfinished_intent, payments.idea_id AS unfinished_payment_idea, " \
            "ideas.title, ideas.short_desc, ideas.price, " \
            "(SELECT files.public_path FROM files WHERE files.id=payments.idea_id ) AS idea_img " \
            "FROM users " \
            "LEFT JOIN files ON users.avatar_id=files.id " \
            "LEFT JOIN payments ON users.id=payments.user_id AND payments.status != 'succeeded' " \
            "AND payments.date > DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 MINUTE)" \
            "LEFT JOIN ideas ON ideas.id=payments.idea_Id " \
            "WHERE users.id=%s"
    cursor.execute(query, (token_data.user_id,))
    result = cursor.fetchone()
    cursor.close()
    if result["unfinished_intent"] is not None:
        intent = stripe.PaymentIntent.retrieve(result["unfinished_intent"], )
        result["unfinished_intent_secret"] = intent["client_secret"]
        return AccountData(
            id=result["id"],
            firstName=result["first_name"],
            lastName=result["last_name"],
            email=result["email"],
            iban=result["iban"],
            username=result["username"],
            dateRegister=result["date_register"],
            dateLogin=result["date_login"],
            avatarURL=result["avatar_url"],
            unfinishedPaymentIntent=result["unfinished_intent"],
            unfinishedPaymentIdeaID=result["unfinished_payment_idea"],
            unfinishedPaymentIdeaTitle=result["title"],
            unfinishedPaymentIdeaShortDesc=result["short_desc"],
            unfinishedPaymentIdeaPrice=result["price"],
            unfinishedPaymentIdeaPictureURL=result["idea_img"],
            unfinishedPaymentIntentSecret=result["unfinished_intent_secret"]
        )

    return AccountData(
        id=result["id"],
        firstName=result["first_name"],
        lastName=result["last_name"],
        email=result["email"],
        iban=result["iban"],
        username=result["username"],
        dateRegister=result["date_register"],
        dateLogin=result["date_login"],
        avatarURL=result["avatar_url"]
    )


@router.put("", response_model=AccountUpdate)
async def update_account(avatar: Optional[UploadFile] = File(None),
                         username: str = Form(None), email: str = Form(None), iban: str = Form(None),
                         pass_hash: str = Form(None), token_data: AccessToken = Depends(get_token_data)):
    is_db_up()
    cursor = db.cursor(dictionary=True)
    result = AccountUpdate(status="none changed")
    if avatar is not None:
        if avatar.content_type not in CDN_ALLOWED_CONTENT_TYPES:
            raise FiletypeNotAllowedError
        temp = await avatar.read()
        async with aiofiles.open(f'{CDN_FILES_PATH + "accounts/" + avatar.filename}',
                                 "wb") as directory:
            await directory.write(temp)
        file_id = hashlib.sha256(temp).hexdigest()
        cursor.execute("INSERT INTO files(id, name, size, absolute_path, public_path, content_type)"
                       "VALUES(%s, %s, %s, %s, %s, %s)",
                       (file_id, avatar.filename, avatar.spool_max_size,
                        f'{CDN_FILES_PATH + "accounts/" + avatar.filename}',
                        f'{CDN_URL + "accounts/" + avatar.filename}', avatar.content_type))
        cursor.execute("UPDATE users SET avatar_id=%s WHERE id=%s", (file_id, token_data.user_id))
        result = AccountUpdate(status="success")
    if username is not None:
        cursor.execute("UPDATE users SET username=%s WHERE id=%s", (username, token_data.user_id))
        token_data.user = username
        result = AccountUpdate(
            status="success",
            token=auth.create_access_token(AccessToken(user_id=token_data.user_id, user=token_data.user))
        )
    if email is not None:
        cursor.execute("UPDATE users SET email=%s WHERE id=%s", (email, token_data.user_id))
        result = AccountUpdate(status="success")
    if iban is not None:
        cursor.execute("UPDATE users SET iban=%s WHERE id=%s", (iban, token_data.user_id))
        result = AccountUpdate(status="success")
    if pass_hash is not None:
        salt = auth.generate_salt()
        cursor.execute(
            "UPDATE users SET salt=%s, pass_hash=%s WHERE id=%s",
            (salt, auth.hash_password(pass_hash, salt), token_data.user_id)
        )
        result = AccountUpdate(
            status="success",
            token=auth.create_access_token(AccessToken(user_id=token_data.user_id, user=token_data.user))
        )
    cursor.close()
    return result


@router.get("/ideas/bought")
async def get_ideas_bought_by_user(page: Optional[int] = 0, token_data: AccessToken = Depends(get_token_data)):
    load_count = 5
    is_db_up()
    cursor = db.cursor(dictionary=True)
    query = "SELECT ideas.*, " \
            "files.public_path AS image_url, " \
            "( SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id ) AS likes " \
            "FROM ideas " \
            "LEFT JOIN files ON ideas.id=files.id " \
            "WHERE buyer_id=%s ORDER BY date_bought DESC LIMIT %s, %s"
    cursor.execute(query, (token_data.user_id, page * load_count, (page + 1) * load_count))
    results = cursor.fetchall()
    for result in results:
        cursor.execute("SELECT category FROM ideas_categories WHERE idea_id=%s", (result["id"],))
        result["categories"] = list(map(lambda x: x["category"], cursor.fetchall()))
        cursor.execute("SELECT * FROM files WHERE idea_id=%s AND idea_id!=id", (result["id"],))
        result["files"] = list(cursor.fetchall())

    # Find the number of ideas matching the criteria
    query = "SELECT COUNT(*) AS ideas_count " \
            "FROM ideas " \
            "WHERE buyer_id=%s"
    cursor.execute(query, (token_data.user_id,))
    ideas_count = cursor.fetchone()["ideas_count"]

    # Calculate remaining ideas for endless scrolling feature
    if page == 0:
        ideas_left = ideas_count - len(results)
    else:
        ideas_left = ideas_count - (page * load_count + len(results))

    cursor.close()

    return BoughtIdeas(
        countLeft=ideas_left,
        ideas=list(map(lambda idea: BoughtIdea(
            id=idea["id"],
            sellerID=idea["seller_id"],
            buyerID=idea["buyer_id"],
            title=idea["title"],
            likes=idea["likes"],
            imageURL=idea["image_url"],
            shortDesc=idea["short_desc"],
            longDesc=idea["long_desc"],
            datePublish=idea["date_publish"],
            dateExpiry=idea["date_expiry"],
            dateBought=idea["date_bought"],
            categories=idea["categories"],
            files=list(map(lambda file: IdeaFile(
                id=file["id"],
                ideaID=file["idea_id"],
                name=file["name"],
                size=file["size"],
                absolutePath=file["absolute_path"],
                publicPath=file["public_path"],
                contentType=file["content_type"],
                uploadDate=file["upload_date"]
            ), result["files"])),
            price=idea["price"]
        ), results))
    )


@router.get("/ideas/sold")
async def get_ideas_bought_by_user(page: Optional[int] = 0, token_data: AccessToken = Depends(get_token_data)):
    load_count = 5

    is_db_up()
    cursor = db.cursor(dictionary=True)
    query = "SELECT ideas.id, seller_id, title, price, date_publish, date_bought, " \
            "files.public_path AS image_url, " \
            "( SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id ) AS likes, " \
            "( SELECT status FROM payouts WHERE idea_id=ideas.id ) AS payout_status " \
            "FROM ideas " \
            "LEFT JOIN files ON ideas.id=files.id " \
            "WHERE seller_id=%s AND buyer_id IS NOT NULL AND buyer_id != -1 " \
            "ORDER BY date_publish ASC LIMIT %s, %s"
    cursor.execute(query, (token_data.user_id, page * load_count, (page + 1) * load_count))
    results = cursor.fetchall()

    # Find the number of ideas matching the criteria
    query = "SELECT COUNT(*) AS ideas_count " \
            "FROM ideas " \
            "WHERE seller_id=%s AND buyer_id IS NOT NULL AND buyer_id != -1"
    cursor.execute(query, (token_data.user_id,))
    ideas_count = cursor.fetchone()["ideas_count"]

    # Calculate remaining ideas for endless scrolling feature
    if len(results) == 0:
        ideas_left = 0
    elif page == 0:
        ideas_left = ideas_count - len(results)
    else:
        ideas_left = ideas_count - (page * load_count + len(results))

    cursor.close()

    return SoldIdeas(
        countLeft=ideas_left,
        ideas=list(map(lambda idea: SoldIdea(
            id=idea["id"],
            sellerID=idea["seller_id"],
            title=idea["title"],
            datePublish=idea["date_publish"],
            dateBought=idea["date_bought"],
            price=idea["price"],
            likes=idea["likes"],
            imageURL=idea["image_url"],
            payoutStatus=idea["payout_status"]
        ), results))
    )


@router.put("/request-payout", response_model=PayoutRequest)
async def request_payout(idea_id: str, _: AccessToken = Depends(get_token_data)):
    verify_idea_id(idea_id)

    cursor = db.cursor(dictionary=True)
    cursor.execute("UPDATE payouts SET status='processing', date=CURRENT_TIMESTAMP() WHERE idea_id=%s", (idea_id,))
    cursor.close()

    return PayoutRequest(status="processing")


@router.get("/invoice/{idea_id}")
async def get_invoice(idea_id: str, token_data: AccessToken = Depends(get_token_data)):
    is_db_up()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT payments.date, payments.status, payments.idea_id, "
                   "ideas.seller_id, ideas.buyer_id, ideas.title, ideas.short_desc, ideas.price, "
                   "CONCAT(users.first_name,' ',users.last_name) as name "
                   "FROM payments "
                   "LEFT JOIN ideas ON payments.idea_id=ideas.id "
                   "LEFT JOIN users ON payments.user_id=users.id "
                   "WHERE payments.idea_id=%s", (idea_id, ))
    result = cursor.fetchone()
    if result is None:
        raise IdeaNotFoundError
    if result["status"] != "succeeded":
        raise InvoiceUnavailableYetError
    if result["buyer_id"] != token_data.user_id:
        if result["seller_id"] != token_data.user_id:
            raise InvoiceAccessUnauthorizedError
        else:
            return Invoice(
                id=result["idea_id"],
                date=result["date"],
                userName=result["name"],
                userType="seller",
                ideaID=result["idea_id"],
                ideaTitle=result["title"],
                ideaPrice=result["price"]
            )
    else:
        return Invoice(
            id=result["idea_id"],
            date=result["date"],
            userName=result["name"],
            userType="buyer",
            ideaID=result["idea_id"],
            ideaTitle=result["title"],
            ideaShortDesc=result["short_desc"],
            ideaPrice=result["price"]
        )


@router.on_event("shutdown")
async def shutdown_event():
    db.close()
