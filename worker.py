import mysql.connector
import stripe
import requests
from datetime import datetime

from app.config import DB_HOST, DB_USER, DB_PASS, DB_NAME, STRIPE_API_KEY, MAILGUN_API_KEY
from app.cache import invalidate_ideas

stripe.api_key = str(STRIPE_API_KEY)


def cleanup_database():
    print("Starting DB cleanup process")

    # New db connection is needed to allow parallel execution
    database = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )
    database.autocommit = True
    cursor = database.cursor(dictionary=True)

    # Find payments that did not go through and the time is up
    cursor.execute(
        "SELECT * FROM payments WHERE status!='succeeded' AND date < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 MINUTE)"
    )
    payments = cursor.fetchall()

    # Remove buy lock from ideas and allow them to be on the marketplace
    for payment in payments:
        stripe.PaymentIntent.cancel(
            stripe.PaymentIntent(payment["id"])
        )
        cursor.execute("DELETE FROM payments WHERE id = %s", (payment["id"],))
        cursor.execute("UPDATE ideas SET buyer_id = NULL WHERE id=%s", (payment["idea_id"],))
    if payments is not None:
        invalidate_ideas()

    # Delete old categories and likes from ideas that were deleted
    cursor.execute("DELETE FROM ideas_categories WHERE idea_id NOT IN (SELECT id FROM ideas)")
    cursor.execute("DELETE FROM ideas_likes WHERE idea_id NOT IN (SELECT id FROM ideas)")

    # Delete users that did not verify their accounts after 15 days, there is check if user has ever logged in, if they
    # have and verified is set to 0, then the account is disabled by the administrators
    cursor.execute(
        "SELECT id, email FROM users "
        "WHERE verified=0 AND date_register < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 15 DAY) AND date_login IS NULL "
    )
    users = cursor.fetchall()
    for user in users:
        cursor.execute("DELETE FROM users WHERE id=%s", (user["id"],))
        requests.post(
            "https://api.eu.mailgun.net/v3/app.creativitycrop.tech/messages",
            auth=("api", str(MAILGUN_API_KEY)),
            data={
                "from": "Friendly Bot from CreativityCrop <no-reply@app.creativitycrop.tech>",
                "to": user.email,
                "subject": "CreativityCrop - Account Deleted",
                "template": "delete-user",
                'h:X-Mailgun-Variables': json.dumps({
                    "user_name": user.first_name,
                    "current_year": datetime.now().year
                })
            }
        )

    # Close cursor and db everything is complete!
    cursor.close()
    database.close()
    print("DB cleaning process is completed!")


if __name__ == "__main__":
    cleanup_database()
