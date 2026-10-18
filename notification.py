"""Notification component - notifies users when an order is created.

In a full system this would be an independent subscriber of the
"Order was created" event. Here it is a small module called by the
Order Service after a successful order, standing in for that event
consumer.
"""

def notify_order_created(order):
    message = (
        f"[notification] OrderCreated event -> notifying user "
        f"'{order['user_id']}' about order {order['order_id']} "
        f"({order['item_id']} x{order['quantity']})"
    )
    print(message, flush=True)
    with open("notifications.log", "a") as f:
        f.write(message + "\n")
