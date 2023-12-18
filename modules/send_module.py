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
    group_id = os.getenv("EMAILS")
    message = "test build apks"

    print(print_utils.warning(f"[{project}] Done email task"))

    