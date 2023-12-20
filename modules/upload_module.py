##############################################
#                                            #
#                Upload module               #
#           Response for operation           #
#           on upload files and folders      #
#                                            #
##############################################
import os

from mega import Mega
from threading import Thread

from modules import send_module
from utils import print_utils


def upload(project, domain, global_time):
    t = Thread(target=lambda: upload_to_mega(project, domain, global_time))
    t.start()


def upload_to_mega(project, domain, global_time):
    mega = Mega()

    workspace_dir = os.getenv('GIT_WORKSPACE')
    project_path = f"{workspace_dir}\\{project}"

    email = os.getenv('MEGA_USERNAME')
    password = os.getenv('MEGA_PASSWORD')
    m = mega.login(email, password)

    app_release_apk = f"{project_path}\\build\\app\\outputs\\flutter-apk\\app-release.apk"
    # Upload the file
    print(print_utils.success(f"[{project}] start upload to MEGA ..."))
    print(print_utils.info(f"[{project}] start upload: {app_release_apk}"))
    file = m.upload(app_release_apk, dest_filename=f"{project}-{domain}-{global_time}.apk")
    file_url = m.get_upload_link(file)
    print(print_utils.info(f"[{project}] File url :: {file_url}"))
    print(print_utils.warning(f"[{project}] Done upload task"))
    send_module.send_to_discord(project,domain, file_url, global_time)
