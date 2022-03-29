from fastapi import APIRouter, Request, Depends
import stripe
import mysql.connector

from app.config import DB_HOST, DB_NAME, DB_PASS, DB_USER, STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET
from app.database import database
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


@router.get("/create", response_model=ClientSecret)
async def create_payment(idea_id: str, token_data: AccessToken = Depends(get_token_data)):
    verify_idea_id(idea_id)

    query = "SELECT " \
            "(SELECT COUNT(*) FROM payments WHERE idea_id=:idea_id) AS idea_count, " \
            "(SELECT COUNT(*) FROM payments WHERE user_id=:user_id AND status != 'succeeded') AS user_count, " \
            "(SELECT user_id FROM payments WHERE idea_id=:idea_id AND status != 'succeeded') AS buyer_id, " \
            "(SELECT id FROM payments WHERE idea_id=:idea_id AND status != 'succeeded') AS payment_id "
    check = await database.fetch_one(query=query, values={"idea_id": idea_id, "user_id": token_data.user_id})

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

    query = "SELECT ideas.price, ideas.title, ideas.seller_id, ideas.buyer_id, users.id AS user_id, users.email " \
            "FROM ideas, users " \
            "WHERE ideas.id=:idea_id AND users.id=:user_id"
    idea = await database.fetch_one(query=query, values={"idea_id": idea_id, "user_id": token_data.user_id})

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
    query = "INSERT INTO payments(id, amount, currency, idea_id, user_id, status) " \
            "VALUES(:id, :amount, :currency, :idea_id, :user_id, :status)"
    await database.execute(
        query=query,
        values={
            "id": intent["id"],
            "amount": intent["amount"],
            "currency": intent["currency"],
            "idea_id": idea_id,
            "user_id": idea["user_id"],
            "status": intent["status"]
        }
    )

    # Make the buyer_id -1 to stop it from appearing in the list of ideas for sale
    await database.execute(query="UPDATE ideas SET buyer_id=-1 WHERE id=:idea_id", values={"idea_id": idea_id})

    return ClientSecret(
        clientSecret=intent["client_secret"]
    )


@router.delete("/cancel")
async def delete_payment(idea_id: str, _: AccessToken = Depends(get_token_data)):
    verify_idea_id(idea_id)

    payment = await database.fetch_one(
        query="SELECT * FROM payments WHERE idea_id=:idea_id",
        values={"idea_id": idea_id}
    )

    if payment is None:
        raise PaymentNotFoundError
    if payment["status"] == "succeeded":
        raise PaymentCannotBeCanceledError

    stripe.PaymentIntent.cancel(
        stripe.PaymentIntent(payment["id"])
    )

    await database.execute(query="DELETE FROM payments WHERE idea_id=:idea_id", values={"idea_id": idea_id})
    await database.execute(query="UPDATE ideas SET buyer_id=NULL WHERE id=:idea_id", values={"idea_id": idea_id})

    return {"status": "success"}


@router.get("/get", response_model=ClientSecret)
async def get_payment(token_data: AccessToken = Depends(get_token_data)):
    result = await database.fetch_one(
        query="SELECT id FROM payments WHERE user_id=:user_id",
        values={"user_id": token_data.user_id}
    )

    if result is None:
        raise PaymentNotFoundError

    intent = stripe.PaymentIntent.retrieve(result["id"], )

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

    await database.execute(
        query="UPDATE payments SET amount=:amount, currency=:currency, status=:status WHERE id=:id",
        values={
            "amount": intent["amount"],
            "currency": intent["currency"],
            "status": intent["status"],
            "id": intent["id"]
        }
    )

    if intent["status"] == "succeeded":
        await database.execute(
            query="UPDATE ideas SET buyer_id=:buyer_id, date_bought=CURRENT_TIMESTAMP() WHERE id=:idea_id",
            values={"buyer_id": intent["metadata"]["buyer_id"], "idea_id": intent["metadata"]["idea_id"]}
        )
        await database.execute(
            query="INSERT INTO payouts(idea_id, user_id) VALUES(:idea_id, :user_id)",
            values={"idea_id": intent["metadata"]["idea_id"], "user_id": intent["metadata"]["seller_id"]}
        )

    return {'status': 'success'}
