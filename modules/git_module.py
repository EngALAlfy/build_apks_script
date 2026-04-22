##############################################
#                                            #
#                 Git module                 #
#           Response for operation           #
#           on pull and push form repos      #
#                                            #
##############################################
import os
import subprocess
from utils import print_utils
import bin.constants

def run_git_command(command, project, task_name, cwd=None):
    if bin.constants.stop_requested:
        raise Exception("Build stopped by user")

    print(print_utils.success(f"[{project}] {task_name} ..."))
    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)
        bin.constants.current_process = process
        
        stdout, stderr = process.communicate()
        
        if bin.constants.stop_requested:
            raise Exception("Build stopped by user")
            
        if process.returncode != 0:
            print(print_utils.danger(f"[{project}] {task_name} FAILED"))
            if stdout: print(print_utils.info(f"STDOUT:\n{stdout}"))
            if stderr: print(print_utils.danger(f"STDERR:\n{stderr}"))
            raise Exception(f"{task_name} failed with exit code {process.returncode}")
            
        print(print_utils.warning(f"[{project}] Done {task_name}"))
        return True
    except Exception as e:
        if bin.constants.stop_requested:
            raise Exception("Build stopped by user")
        raise e
    finally:
        bin.constants.current_process = None


def git_clone(project):
    use_token = os.getenv('GIT_USE_TOKEN', 'false').lower() == "true"
    workspace_dir = os.getenv('GIT_WORKSPACE')
    
    if not workspace_dir:
        print(print_utils.danger(f"[{project}] GIT_WORKSPACE not set"))
        return

    # Normalize path and ensure it exists
    workspace_dir = os.path.abspath(workspace_dir)
    if not os.path.exists(workspace_dir):
        print(print_utils.info(f"Creating workspace: {workspace_dir}"))
        os.makedirs(workspace_dir, exist_ok=True)

    project_path = os.path.join(workspace_dir, project)
    user = os.getenv('GIT_USER')
    token = os.getenv('GIT_TOKEN')
    branch = os.getenv('GIT_BRANCH', 'main')
    
    # Check if the repo exists
    if os.path.isdir(project_path) and os.path.exists(os.path.join(project_path, ".git")):
        print(print_utils.info(f"[{project}] Repo exists, pulling updates..."))
        run_git_command("git restore .", project, "git restore", cwd=project_path)
        run_git_command(f"git pull origin {branch}", project, "git pull", cwd=project_path)
    else:
        print(print_utils.info(f"[{project}] Repo not found, cloning..."))
        if use_token and token:
            url = f"https://{user}:{token}@github.com/{user}/{project}.git"
        else:
            url = f"https://github.com/{user}/{project}.git"
        
        run_git_command(f"git clone --single-branch --branch {branch} {url}", project, "git clone", cwd=workspace_dir)
            
    if not os.path.isdir(project_path):
        raise FileNotFoundError(f"Project directory {project_path} not found after git operation")
    
    # Final check: move to project path for subsequent flutter commands
    os.chdir(project_path)
