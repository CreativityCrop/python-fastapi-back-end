import mysql.connector
import stripe

from config import DB_HOST, DB_USER, DB_PASS, DB_NAME, STRIPE_API_KEY

stripe.api_key = str(STRIPE_API_KEY)


# TODO: Add user cleanup
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

    # Delete old categories and likes from ideas that were deleted
    cursor.execute("DELETE FROM ideas_categories WHERE idea_id NOT IN (SELECT id FROM ideas)")
    cursor.execute("DELETE FROM ideas_likes WHERE idea_id NOT IN (SELECT id FROM ideas)")

    # Close cursor and db everything is complete!
    cursor.close()
    database.close()
    print("DB cleaning process is completed!")


if __name__ == "__main__":
    cleanup_database()
