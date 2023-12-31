##############################################
#                                            #
#                Send module                 #
#           Response for operation           #
#           on send files to testers         #
#                                            #
##############################################
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from utils import print_utils


def send_to_email(project, file_url):
    print(print_utils.success(f"[{project}] start send to email ..."))
    emails = os.getenv("EMAILS")

    if emails:
        emails = emails.split(',')
    else:
        print(print_utils.danger(f"[{project}] No emails"))
        return

    # Email account information
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    smtp_host = os.getenv("SMTP_HOST")

    # Create the MIME object
    message = MIMEMultipart()
    message['From'] = sender_email.split("@").pop(0)
    message['Subject'] = f"{project} APKs"

    # Body of the email
    body = f"This is email with {project} release apk for testing \n APK url: {file_url}"
    message.attach(MIMEText(body, 'plain'))

    # Establish a connection with the SMTP server
    with smtplib.SMTP(smtp_host, 587) as server:
        server.starttls()  # Use TLS for security
        server.login(sender_email, sender_password)

        for email in emails:
            message['To'] = email
            # Send the email
            server.sendmail(sender_email, email, message.as_string())


    message = "test build apks"
    print(print_utils.warning(f"[{project}] Done email task"))


def send_to_discord(project, domain, file_url, global_time):
    is_enabled = os.getenv('DISCORD_ENABLED')
    if is_enabled == True:
        print(print_utils.success(f"[{project}] start send to discord ..."))
        url = os.getenv("DISCORD_WEBHOOK")

        if url is None:
            print(print_utils.danger(f"[{project}] No discord webhook"))
            return

        # Body of the message
        body = f"⏰ **[{global_time}]** \n **[{project}]** release apk for testing ✔📱 \n **[{project}]** Domain: {domain} \n **[{project}]** APK url: {file_url} \n"

        response = requests.post(url, json={"content": body})
        print(print_utils.warning(f"[{project}] Done discord task"))

