##############################################
#                                            #
#               Flutter module               #
#           Response for operation           #
#           on build flutter projects        #
#                                            #
##############################################
import subprocess
from utils import print_utils, commands_utils
import bin.constants

def run_command(command, project, task_name, ignore_errors=False):
    if bin.constants.stop_requested:
        raise Exception("Build stopped by user")
    
    print(print_utils.success(f"[{project}] {task_name} ..."))
    try:
        # Use shell=True for Windows compatibility with complex commands
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
        bin.constants.current_process = process
        
        stdout, stderr = process.communicate()
        
        if bin.constants.stop_requested:
            raise Exception("Build stopped by user")
            
        if process.returncode != 0:
            if ignore_errors:
                print(print_utils.warning(f"[{project}] {task_name} FAILED but allowed to fail. Skipping..."))
                return False
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


def clean(project):
    run_command(commands_utils.FLUTTER_CLEAN_COMMAND, project, "flutter clean")


def pub_get(project):
    run_command(commands_utils.FLUTTER_PUB_GET_COMMAND, project, "flutter pub get")


def intl_generate(project):
    success = run_command(commands_utils.FLUTTER_INTL_GENERATE_COMMAND, project, "flutter intl generate", ignore_errors=True)
    if not success:
        print(print_utils.warning(f"[{project}] intl_utils not found or failed. Attempting to add intl_utils..."))
        add_success = run_command("flutter pub add intl_utils", project, "flutter pub add intl_utils", ignore_errors=True)
        if add_success:
            run_command(commands_utils.FLUTTER_INTL_GENERATE_COMMAND, project, "flutter intl generate (retry)")
        else:
            print(print_utils.danger(f"[{project}] Failed to add intl_utils. Localization might be skipped."))


def build_debug(project):
    run_command(commands_utils.FLUTTER_BUILD_DEBUG_COMMAND, project, "flutter build debug")


def build_release(project):
    run_command(commands_utils.FLUTTER_BUILD_RELEASE_COMMAND, project, "flutter build release")


def build_appbundle(project):
    run_command(commands_utils.FLUTTER_BUILD_APPBUNDLE_COMMAND, project, "flutter build appbundle")