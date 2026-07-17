import smtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
load_dotenv()

def send_order_notification(order_data: dict):
    sender = os.getenv("GMAIL_USER")
    password = os.getenv("GMAIL_APP_PASSWORD")
    receiver = sender  # toi-même

    body = f"""Nouvelle commande PureForce Bleach !

Client: {order_data.get('name')}
Email: {order_data.get('email')}
Téléphone: {order_data.get('phone')}
Produit: {order_data.get('product')}
Quantité: {order_data.get('quantity')}
Adresse: {order_data.get('address')}
"""
    msg = MIMEText(body)
    msg['Subject'] = '🛒 Nouvelle commande PureForce Bleach'
    msg['From'] = sender
    msg['To'] = receiver

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())