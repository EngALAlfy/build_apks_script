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


def send_to_email(project, file_urls, global_time):
    if os.getenv('EMAIL_ENABLED', 'false').lower() != "true":
        print(print_utils.danger(f"[{project}] Email notifications disabled"))
        return

    print(print_utils.success(f"[{project}] Sending email notification ..."))
    emails = os.getenv("EMAILS")

    if not emails:
        print(print_utils.danger(f"[{project}] No email recipients found"))
        return
    
    emails = emails.split(',')
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    if not all([sender_email, sender_password, smtp_host]):
        print(print_utils.danger(f"[{project}] Email configuration incomplete"))
        return

    try:
        # Create the MIME object
        message = MIMEMultipart()
        message['From'] = f"APK Builder <{sender_email}>"
        message['Subject'] = f"🚀 {project} - New Build Available ({global_time})"

        # Body of the email
        links_text = "\n".join([f"- {k.upper()}: {v}" for k, v in file_urls.items()])
        body = f"""
Hello,

A new build of {project} has been completed successfully.

Build Details:
- Project: {project}
- Time: {global_time}

Download Links:
{links_text}

Regards,
APK Builder System
"""
        message.attach(MIMEText(body, 'plain'))

        # Establish a connection with the SMTP server
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            for email in emails:
                message['To'] = email.strip()
                server.sendmail(sender_email, email.strip(), message.as_string())

        print(print_utils.warning(f"[{project}] Email notification sent"))
    except Exception as e:
        print(print_utils.danger(f"[{project}] Email failed: {e}"))


def send_to_discord(project, file_urls, global_time):
    if os.getenv('DISCORD_ENABLED', 'false').lower() != "true":
        print(print_utils.danger(f"[{project}] Discord notifications disabled"))
        return

    print(print_utils.success(f"[{project}] Sending Discord notification ..."))
    url = os.getenv("DISCORD_WEBHOOK")

    if not url:
        print(print_utils.danger(f"[{project}] No Discord webhook found"))
        return

    try:
        links_text = "\n".join([f"🔗 **{k.upper()}**: {v}" for k, v in file_urls.items()])
        
        # Body of the message
        content = (
            f"🚀 **New Build Alert: {project}**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 **Time**: `{global_time}`\n\n"
            f"📥 **Download Links**:\n"
            f"{links_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        requests.post(url, json={"content": content})
        print(print_utils.warning(f"[{project}] Discord notification sent"))
    except Exception as e:
        print(print_utils.danger(f"[{project}] Discord failed: {e}"))

