import os
import shutil
import yaml
import json
import sys
from datetime import datetime

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


##############################################
#                                            #
#                  Config                    #
#                                            #
##############################################

# Base path of projects
BASE_DIR = "E:\\flutter"

# Define the directory path
directory_path = f'{BASE_DIR}\\$$'
build_apk_debug_path = f'{BASE_DIR}\\$$\\build\\app\\outputs\\flutter-apk\\app-debug.apk'
build_apk_release_path = f'{BASE_DIR}\\$$\\build\\app\\outputs\\flutter-apk\\app-release.apk'
build_aab_path = f'{BASE_DIR}\\$$\\build\\app\\outputs\\bundle\\release\\app-release.aab '
builds_path = f'\\\\server\\Operator\\Operators\\HurryApp\\Apk\'s\\Quick Apk\\{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}\\$$\\{"beta" if "beta" in sys.argv[1:] else "backend"}'
# Define the projects names
projects = ["hurryApp", "restaurant_manager", "BranchManager", "delivery_captin"]

# Line
LINE = '*' * 50


##############################################
#                                            #
#                  Functions                 #
#                                            #
##############################################


def change_git_branch(project):
    print(f"{bcolors.OKGREEN}[{project}] Change GIT branch{bcolors.ENDC}")
    os.system("git pull ori development")


def change_domains(project):
    print(f"{bcolors.OKGREEN}[{project}] Change domain{bcolors.ENDC}")
    # Load the JSON file
    with open('assets\\cfg\\configurations.json', 'r') as file:
        data = json.load(file)

    # Modify the value of the "url" key
    if "beta" in sys.argv[1:]:
        print(f"{bcolors.OKBLUE}[{project}] Change domain to BETA1{bcolors.ENDC}")
        data['base_url'] = 'https://beta1.hurryapps.com/'
        data['api_base_url'] = 'https://beta1.hurryapps.com/api/'
    else:
        print(f"{bcolors.OKBLUE}[{project}] Change domain to BACKEND{bcolors.ENDC}")
        data['base_url'] = 'https://backend.hurryapps.com/'
        data['api_base_url'] = 'https://backend.hurryapps.com/api/'

    # Save the modified data back to the file
    with open('assets\\cfg\\configurations.json', 'w') as file:
        json.dump(data, file, indent=4)


def build_flutter(project):
    # Run 'flutter clean' command
    print(f"{bcolors.OKGREEN}[{project}] Start clean{bcolors.ENDC}")
    os.system('flutter clean')

    # Run 'flutter build apk --debug' command
    print(f"{bcolors.OKGREEN}[{project}] Start build debug apk{bcolors.ENDC}")
    os.system('flutter build apk --debug')

    # Run 'flutter build apk --release' command
    print(f"{bcolors.OKGREEN}[{project}] Start build release apk{bcolors.ENDC}")
    os.system('flutter build apk --release')

    # Run 'flutter build appbundle' command
    print(f"{bcolors.OKGREEN}[{project}] Start build appbundle{bcolors.ENDC}")
    os.system('flutter build appbundle')

    # Done
    print(f"{bcolors.OKBLUE}{LINE}{bcolors.ENDC}")


def copy_builds(project):
    print(f"{bcolors.OKGREEN}[{project}] Copy files{bcolors.ENDC}")
    # create build dir
    os.makedirs(builds_path.replace("$$", project), 511, True)
    # copy apk debug
    file_path = build_apk_debug_path.replace("$$", project)
    new_file_path = builds_path.replace("$$", project)
    shutil.copy2(file_path, new_file_path)
    # copy apk release
    file_path = build_apk_release_path.replace("$$", project)
    new_file_path = builds_path.replace("$$", project)
    shutil.copy2(file_path, new_file_path)
    # copy appbundle
    file_path = build_aab_path.replace("$$", project)
    new_file_path = builds_path.replace("$$", project)
    shutil.copy2(file_path, new_file_path)


def rename_builds(project):
    print(f"{bcolors.OKGREEN}[{project}] Rename builds {bcolors.ENDC}")
    with open('pubspec.yaml', 'r') as file:
        pubspec_content = yaml.safe_load(file)
    version = pubspec_content.get('version')
    if version:
        project_builds_path = builds_path.replace("$$", project)
        os.rename(f"{project_builds_path}/app-debug.apk", f"{project_builds_path}/{project}_{version}_debug.apk")
        os.rename(f"{project_builds_path}/app-release.apk", f"{project_builds_path}/{project}_{version}_release.apk")
        os.rename(f"{project_builds_path}/app-release.aab", f"{project_builds_path}/{project}_{version}_release.aab")
        print(f"{bcolors.OKBLUE}[{project}] Rename Done {bcolors.ENDC}")
    else:
        print(f"{bcolors.FAIL}[{project}] Version not found {bcolors.ENDC}")


def print_msg_box(msg, indent=1, width=None, title=None, color=bcolors.BOLD):
    """Print message-box with optional title."""
    lines = msg.split('\n')
    space = " " * indent
    if not width:
        width = max(map(len, lines))
    box = f'╔{"═" * (width + indent * 2)}╗\n'  # upper_border
    if title:
        box += f'║{space}{title:<{width}}{space}║\n'  # title
        box += f'║{space}{"-" * len(title):<{width}}{space}║\n'  # underscore
    box += ''.join([f'║{space}{line:<{width}}{space}║\n' for line in lines])
    box += f'╚{"═" * (width + indent * 2)}╝'  # lower_border
    print(f"{color}{box}{bcolors.ENDC}")


##############################################
#                                            #
#                  Start                     #
#                                            #
##############################################

print_msg_box("\n Building APKs Script V1 \n Author : Islam H Alalafy \n To stop script press CTRL + C \n",
              color=bcolors.OKBLUE, indent=10)
print("\n")
print(f"{bcolors.WARNING}Start building APKs... {bcolors.ENDC}")
print("\n")

try:
    for project in projects:
        print_msg_box(f"\n [{project}] \n Start building APKs for {project} \n", color=bcolors.OKCYAN, indent=10)
        print("\n")
        print("\n")
        project_path = directory_path.replace("$$", project)
        os.chdir(project_path)
        print(f"{bcolors.OKGREEN}[{project}] Current path: [{project_path}]{bcolors.ENDC}")
        # change_git_branch(project)
        change_domains(project)
        build_flutter(project)
        copy_builds(project)
        rename_builds(project)

        # Done
        print_msg_box(f"\n [{project}] \n building APKs for {project} done \n", color=bcolors.OKGREEN, indent=10)
        print(f"{bcolors.FAIL}{LINE}{bcolors.ENDC}")
        print("\n")
        print("\n")

except KeyboardInterrupt:
    print(f"{bcolors.FAIL}{LINE}{bcolors.ENDC}")
    print(f"{bcolors.FAIL}Script ended munally with CTRL + C{bcolors.ENDC}")
    print(f"{bcolors.FAIL}{LINE}{bcolors.ENDC}")
    raise SystemExit
