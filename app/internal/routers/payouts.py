from fastapi import APIRouter

from app.database import database
from app.internal.responses.payouts import Payout, PayoutsList

router = APIRouter(
    prefix="/payouts",
)


@router.get("/", response_model=PayoutsList)
async def get_payouts():
    payouts = await database.fetch_all(
        query="SELECT payouts.*, users.first_name, users.last_name, users.iban, payments.amount "
              "FROM payouts "
              "LEFT JOIN users ON users.id=payouts.user_id "
              "LEFT JOIN payments ON payments.idea_id=payouts.idea_id "
              "ORDER BY payouts.date, payouts.date_paid DESC"
    )

    return PayoutsList(
        payouts=list(map(lambda payout: Payout(
            userID=payout["user_id"],
            userFirstName=payout["first_name"],
            userLastName=payout["last_name"],
            ideaID=payout["idea_id"],
            date=payout["date"],
            datePaid=payout["date_paid"],
            status=payout["status"],
            amount=payout["amount"],
            iban=payout["iban"]
        ), payouts))
    )


# Endpoint to set payout status to completed
@router.put("/{idea_id}/complete", response_model=Payout)
async def complete_payout(idea_id: str):
    await database.execute(
        query="UPDATE payouts SET date_paid=CURRENT_TIMESTAMP(), status='completed' WHERE idea_id=:idea_id",
        values={"idea_id": idea_id}
    )

    return {"status": "success"}


# Endpoint to set payout status to completed
@router.put("/{idea_id}/denied", response_model=Payout)
async def complete_payout(idea_id: str):
    await database.execute(
        query="UPDATE payouts SET status='denied' WHERE idea_id=:idea_id",
        values={"idea_id": idea_id}
    )

    return {"status": "success"}
