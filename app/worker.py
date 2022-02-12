from mysql import connector
import stripe
import datetime

from app.config import *

stripe.api_key = str(STRIPE_API_KEY)


class DatabaseCleanupWorker:
    worker_next_run = datetime.date(1970, 1, 1)

    def cleanup_database(self):
        # Set variable to keep next run time
        self.worker_next_run = datetime.datetime.now() + DB_CLEANUP_INTERVAL
        print("Starting DB cleanup process")

        # New db connection is needed to allow parallel execution
        second_db = connector.connect(
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
