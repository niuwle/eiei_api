# In app/utils/payment_processor.py

import stripe
from app.config import STRIPE_API_KEY

stripe.api_key = STRIPE_API_KEY

def create_payment_intent(amount, currency='usd'):
    return stripe.PaymentIntent.create(
        amount=amount,
        currency=currency,
        payment_method_types=['card'],
    )
