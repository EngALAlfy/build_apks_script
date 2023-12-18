##############################################
#                                            #
#                Send module                 #
#           Response for operation           #
#           on send files to testers         #
#                                            #
##############################################
import os


from utils import print_utils


def send_to_email(project, file_url):
    print(print_utils.success(f"[{project}] start send to email ..."))
    emails = os.getenv("EMAILS")

    if emails:
        emails = emails.split(',')
    else:
        print(print_utils.danger(f"[{project}] No emails"))
        return

    message = "test build apks"
    print(print_utils.warning(f"[{project}] Done email task"))

    