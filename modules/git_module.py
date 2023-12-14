##############################################
#                                            #
#                 Git module                 #
#           Response for operation           #
#           on pull and push form repos      #
#                                            #
##############################################
import os


def git_clone(project):
    workspace_dir = os.getenv('GIT_WORKSPACE')
    os.chdir(workspace_dir)

    # clean any repo first
    os.system(f"rmdir /s /q {project}")

    user = os.getenv('GIT_USER')
    token = os.getenv('GIT_TOKEN')
    branch = os.getenv('GIT_BRANCH')

    git_clone_command = f"git clone --single-branch --branch {branch} https://{user}:{token}@github.com/{user}/{project}.git"
    os.system(git_clone_command)
    os.chdir(f"{workspace_dir}\\{project}")
