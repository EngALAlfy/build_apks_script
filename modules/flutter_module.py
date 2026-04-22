##############################################
#                                            #
#               Flutter module               #
#           Response for operation           #
#           on build flutter projects        #
#                                            #
##############################################
import subprocess
from utils import print_utils, commands_utils


def run_command(command, project, task_name):
    print(print_utils.success(f"[{project}] {task_name} ..."))
    try:
        # Use shell=True for Windows compatibility with complex commands
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(print_utils.warning(f"[{project}] Done {task_name}"))
        return True
    except subprocess.CalledProcessError as e:
        print(print_utils.danger(f"[{project}] {task_name} FAILED"))
        if e.stdout: print(print_utils.info(f"STDOUT:\n{e.stdout}"))
        if e.stderr: print(print_utils.danger(f"STDERR:\n{e.stderr}"))
        raise Exception(f"{task_name} failed with exit code {e.returncode}")


def clean(project):
    run_command(commands_utils.FLUTTER_CLEAN_COMMAND, project, "flutter clean")


def pub_get(project):
    run_command(commands_utils.FLUTTER_PUB_GET_COMMAND, project, "flutter pub get")


def intl_generate(project):
    run_command(commands_utils.FLUTTER_INTL_GENERATE_COMMAND, project, "flutter intl generate")


def build_debug(project):
    run_command(commands_utils.FLUTTER_BUILD_DEBUG_COMMAND, project, "flutter build debug")


def build_release(project):
    run_command(commands_utils.FLUTTER_BUILD_RELEASE_COMMAND, project, "flutter build release")


def build_appbundle(project):
    run_command(commands_utils.FLUTTER_BUILD_APPBUNDLE_COMMAND, project, "flutter build appbundle")