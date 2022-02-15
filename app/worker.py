import mysql.connector
import stripe

DB_HOST = 'localhost'
DB_USER = 'creativity_crop'
DB_PASS = 'qO4n3BPtA4MgStJW'
DB_NAME = 'creativity_crop'

stripe.api_key = 'sk_test_51Jx4d2Ldhfi7be41P1vPbJ4zd47yIWOii662BD9HIqUK14y3N8p57jbIt6sCKHNra0U1NzkAnZeaBUjHyZjRO' \
                 'Yg300EhrWWoMB'


def cleanup_database():
    print("Starting DB cleanup process")

    # New db connection is needed to allow parallel execution
    second_db = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )
    second_db.autocommit = True
    second_cursor = second_db.cursor(dictionary=True)
    # Find payments that did not go through and the time is up
    second_cursor.execute("SELECT * FROM payments "
                          "WHERE status!='succeeded' AND date < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 MINUTE)")
    payments = second_cursor.fetchall()
    # Remove buy lock from ideas and allow them to be on the marketplace
    for payment in payments:
        second_cursor.execute("UPDATE ideas SET buyer_id = NULL WHERE id=%s", (payment["idea_id"],))
        stripe.PaymentIntent.cancel(
            stripe.PaymentIntent(payment["id"])
        )
        second_cursor.execute("DELETE FROM payments WHERE id = %s", (payment["id"],))
    # Delete old categories and likes from ideas that were deleted
    second_cursor.execute("DELETE FROM ideas_categories WHERE idea_id NOT IN (SELECT id FROM ideas)")
    second_cursor.execute("DELETE FROM ideas_likes WHERE idea_id NOT IN (SELECT id FROM ideas)")
    # Close cursor and db everything is complete!
    second_cursor.close()
    second_db.close()
    print("DB cleaning process is completed!")


if __name__ == "__main__":
    cleanup_database()
