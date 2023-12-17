##############################################
#                                            #
#                Upload module               #
#           Response for operation           #
#           on upload files and folders      #
#                                            #
##############################################
import os

from mega import Mega


def upload_to_mega(project):
    mega = Mega()

    user = os.getenv('GIT_USER')
    workspace_dir = os.getenv('GIT_WORKSPACE')
    project_path = f"{workspace_dir}\\{project}"

    email = os.getenv('GIT_WORKSPACE')
    password = os.getenv('GIT_WORKSPACE')
    m = mega.login(email, password)

    # Specify the target folder on MEGA where you want to upload the file
    mega_folder = f'{user}/{project}'

    # Upload the file
    file = m.upload(project_path, dest_path=mega_folder)
    