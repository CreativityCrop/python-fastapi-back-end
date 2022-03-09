from fastapi import APIRouter, Request, Depends
import stripe
import mysql.connector

from app.config import DB_HOST, DB_NAME, DB_PASS, DB_USER, STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET
from app.dependencies import get_token_data
from app.functions import verify_idea_id
from app.errors.payment import *
from app.errors.ideas import IdeaNotFoundError
from app.models.token import AccessToken
from app.responses.payment import ClientSecret

router = APIRouter(
    prefix="/payment",
    tags=["payment"],
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


@router.get("/create", response_model=ClientSecret)
async def create_payment(idea_id: str, token_data: AccessToken = Depends(get_token_data)):
    verify_idea_id(idea_id)

    is_db_up()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT "
        "(SELECT COUNT(*) FROM payments WHERE idea_id=%s) AS idea_count, "
        "(SELECT COUNT(*) FROM payments WHERE user_id=%s AND status != 'succeeded') AS user_count, "
        "(SELECT user_id FROM payments WHERE idea_id=%s AND status != 'succeeded') AS buyer_id, "
        "(SELECT id FROM payments WHERE idea_id=%s AND status != 'succeeded') AS payment_id ",
        (idea_id, token_data.user_id, idea_id, idea_id)
    )
    check = cursor.fetchone()
    # Payment already exists for that idea
    if check["idea_count"] != 0:
        # Check if user is the initiator of the payment
        if check["buyer_id"] == token_data.user_id:
            # If yes, give them the payment
            intent = stripe.PaymentIntent.retrieve(check["payment_id"], )
            return ClientSecret(
                clientSecret=intent["client_secret"]
            )
        else:
            raise IdeaBusyError
    # User already has an unfinished payment, cannot make another
    if check["user_count"] != 0:
        raise UnresolvedPaymentExistsError

    cursor.execute("SELECT ideas.price, ideas.title, ideas.seller_id, ideas.buyer_id, users.id AS user_id, users.email "
                   "FROM ideas, users "
                   "WHERE ideas.id=%s AND users.id=%s",
                   (idea_id, token_data.user_id))
    idea = cursor.fetchone()

    if idea is None:
        raise IdeaNotFoundError
    # Checks if idea is for sale
    if idea["buyer_id"] is not None:
        raise IdeaAlreadySoldError

    intent = stripe.PaymentIntent.create(
        amount=int(idea["price"] * 100),
        receipt_email=idea["email"],
        currency="usd",
        description="CreativityCrop - Selling the idea: " + idea["title"],
        metadata={
            "idea_id": idea_id,
            "seller_id": idea["seller_id"],
            "buyer_id": token_data.user_id
        }

    )
    cursor.execute("INSERT INTO payments(id, amount, currency, idea_id, user_id, status) "
                   "VALUES(%s, %s, %s, %s, %s, %s)",
                   (intent["id"], intent["amount"], intent["currency"], idea_id, idea["user_id"], intent["status"]))
    # Make the buyer_id -1 to stop it from appearing in the list of ideas for sale
    cursor.execute("UPDATE ideas SET buyer_id=-1 WHERE id=%s", (idea_id,))
    cursor.close()
    return ClientSecret(
        clientSecret=intent["client_secret"]
    )


@router.delete("/cancel")
async def delete_payment(idea_id: str, _: AccessToken = Depends(get_token_data)):
    verify_idea_id(idea_id)
    is_db_up()

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM payments WHERE idea_id=%s", (idea_id,))
    payment = cursor.fetchone()

    if payment is None:
        raise PaymentNotFoundError
    if payment["status"] == "succeeded":
        raise PaymentCannotBeCanceledError

    stripe.PaymentIntent.cancel(
        stripe.PaymentIntent(payment["id"])
    )

    cursor.execute("DELETE FROM payments WHERE idea_id=%s", (idea_id,))
    cursor.execute("UPDATE ideas SET buyer_id=NULL WHERE id=%s", (idea_id,))

    cursor.close()

    return {"status": "success"}


@router.get("/get", response_model=ClientSecret)
def get_payment(token_data: AccessToken = Depends(get_token_data)):
    is_db_up()

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM payments WHERE user_id=%s", (token_data.user_id,))
    result = cursor.fetchone()

    if result is None:
        raise PaymentNotFoundError

    intent = stripe.PaymentIntent.retrieve(result["id"], )

    cursor.close()

    return ClientSecret(
        clientSecret=intent["client_secret"]
    )


# Webhook code provided by Stripe
@router.post('/webhook')
async def webhook_received(request: Request):
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = str(STRIPE_WEBHOOK_SECRET)
    try:
        event = stripe.Webhook.construct_event(await request.body(), sig_header, webhook_secret)
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ex.__dict__)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"text": "Invalid signature"})

    is_db_up()
    cursor = db.cursor(dictionary=True)
    intent = {}
    if event['type'] == 'payment_intent.canceled':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.payment_failed':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.processing':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.requires_action':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
    else:
        print('Unhandled event type {}'.format(event['type']))
    cursor.execute(
        "UPDATE payments SET amount=%s, currency=%s, status=%s WHERE id=%s",
        (intent["amount"], intent["currency"], intent["status"], intent["id"])
    )
    if intent["status"] == "succeeded":
        cursor.execute(
            "UPDATE ideas SET buyer_id=%s, date_bought=CURRENT_TIMESTAMP() WHERE id=%s",
            (intent["metadata"]["buyer_id"], intent["metadata"]["idea_id"])
        )
        cursor.execute(
            "INSERT INTO payouts(idea_id, user_id) VALUES(%s, %s)",
            (intent["metadata"]["idea_id"], intent["metadata"]["seller_id"])
        )
    cursor.close()

    return {'status': 'success'}


@router.on_event("shutdown")
async def shutdown_event():
    db.close()
