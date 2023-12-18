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

    