# email_sender.py
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import SENDER_EMAIL, RECEIVER_EMAIL, EMAIL_PASSWORD

def send_email(final_solution: str):
    email_body = f"""<html>
  <head>
    <style>
      body {{ font-family: Arial, sans-serif; line-height: 1.6; padding: 10px; }}
      h2 {{ color: #2E86C1; border-bottom: 1px solid #ccc; padding-bottom: 5px; }}
      p {{ margin: 10px 0; }}
    </style>
  </head>
  <body>
    {final_solution}
  </body>
</html>"""
    message = MIMEMultipart('alternative')
    message['Subject'] = 'Defect RCA'
    message['From'] = SENDER_EMAIL
    message['To'] = RECEIVER_EMAIL
    message.attach(MIMEText(email_body, 'html'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Error in sending email: {e}")
