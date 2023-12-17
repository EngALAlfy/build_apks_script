##############################################
#                                            #
#                 Git module                 #
#           Response for operation           #
#           on pull and push form repos      #
#                                            #
##############################################
import os


def git_clone(project):
    use_token = os.getenv('GIT_USE_TOKEN') == "true"

    workspace_dir = os.getenv('GIT_WORKSPACE')

    project_path = f"{workspace_dir}\\{project}"

    user = os.getenv('GIT_USER')
    token = os.getenv('GIT_TOKEN')
    branch = os.getenv('GIT_BRANCH')

    os.chdir(project_path)

    # check if the repo exist
    if os.path.isdir(project_path) and os.listdir(project_path):
        # run restore first
        git_clone_command = f"git restore ."
        os.system(git_clone_command)
        # run pull from branch
        git_clone_command = f"git pull origin {branch}:{branch}"
    else:
        if use_token:
            git_clone_command = f"git clone --single-branch --branch {branch} https://{user}:{token}@github.com/{user}/{project}.git ."
        else:
            git_clone_command = f"git clone --single-branch --branch {branch} https://github.com/{user}/{project}.git ."

    os.system(git_clone_command)

