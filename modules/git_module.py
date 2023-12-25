##############################################
#                                            #
#                 Git module                 #
#           Response for operation           #
#           on pull and push form repos      #
#                                            #
##############################################
import os

from utils import print_utils


def git_clone(project):
    print(print_utils.success(f"[{project}] start git update ..."))
    use_token = os.getenv('GIT_USE_TOKEN') == "true"

    workspace_dir = os.getenv('GIT_WORKSPACE')

    project_path = f"{workspace_dir}\\{project}"

    user = os.getenv('GIT_USER')
    token = os.getenv('GIT_TOKEN')
    branch = os.getenv('GIT_BRANCH')
    
    os.chdir(workspace_dir)
    
    # check if the repo exist
    if os.path.isdir(project_path) and os.listdir(project_path):
        os.chdir(project_path)
        # run restore first
        git_clone_command = f"git restore ."
        os.system(git_clone_command)
        # run pull from branch
        git_clone_command = f"git pull origin {branch}:{branch}"
        os.system(git_clone_command)
    else:
        if use_token:
            git_clone_command = f"git clone --single-branch --branch {branch} https://{user}:{token}@github.com/{user}/{project}.git"
        else:
            git_clone_command = f"git clone --single-branch --branch {branch} https://github.com/{user}/{project}.git"
        os.system(git_clone_command)
        os.chdir(project_path)
          
        
    print(print_utils.warning(f"[{project}] Done git task"))

