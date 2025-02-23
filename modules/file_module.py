##############################################
#                                            #
#                 File module                #
#           Response for operation           #
#           on build files and folders       #
#                                            #
##############################################
import json
import os
import shutil
from datetime import datetime

import yaml

from utils import print_utils


def change_domain(project, domain):
    print(print_utils.success(f"[{project}] Change domain to [{domain}]"))
    try:
        # Load the JSON file
        with open('assets/cfg/production_config.json', 'r') as file:
            data = json.load(file)

        # Modify the value of the "url" key
        data['base_url'] = f'https://{domain}.hurryapps.com/'
        data['api_base_url'] = f'https://{domain}.hurryapps.com/api/'

        # Save the modified data back to the file
        with open('assets/cfg/production_config.json', 'w') as file:
            json.dump(data, file, indent=4)

    except FileNotFoundError:
        print(print_utils.danger(f"[{project}] Cannot find configurations file ..."))


def copy_files(project, domain , global_time, build_type):
    print(print_utils.success(f"[{project}] start copy files ..."))
    result_path = os.getenv("RESULT_WORKSPACE")
    workspace_dir = os.getenv('GIT_WORKSPACE')
    project_path = f"{workspace_dir}\\{project}"

    with open('pubspec.yaml', 'r') as file:
        pubspec_content = yaml.safe_load(file)
    version = pubspec_content.get('version')

    if version is None:
        version = "1.0"

    if build_type == 'appbundle':
        # copy app bundle
        new_file_path = f"{result_path}\\{global_time}\\{project}-{domain}"
        new_file = f"{new_file_path}\\{project}-{domain}-{version}-{build_type}.aap"
        # create build dir
        os.makedirs(new_file_path, 511, True)
        app_file = f"{project_path}\\build\\app\\outputs\\bundle\\release\\app-release.aap"
        shutil.copy2(app_file, new_file)
    else:
        # copy debug apk
        new_file_path = f"{result_path}\\{global_time}\\{project}-{domain}"
        extension = 'aap' if build_type == 'appbundle' else 'apk'
        new_file = f"{new_file_path}\\{project}-{domain}-{version}-{build_type}.{extension}"
        # create build dir
        os.makedirs(new_file_path, 511, True)
        app_file = f"{project_path}\\build\\app\\outputs\\flutter-apk\\app-{build_type}.apk"
        shutil.copy2(app_file, new_file)

    print(print_utils.warning(f"[{project}] Done copy task"))
    return new_file
