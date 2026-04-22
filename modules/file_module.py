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


def copy_files(project, global_time, build_type):
    print(print_utils.success(f"[{project}] start copy files ..."))
    result_path = os.getenv("RESULT_WORKSPACE")
    workspace_dir = os.getenv('GIT_WORKSPACE')
    project_path = f"{workspace_dir}\\{project}"

    # Get version from pubspec.yaml
    version = "1.0"
    try:
        pubspec_path = os.path.join(project_path, 'pubspec.yaml')
        if os.path.exists(pubspec_path):
            with open(pubspec_path, 'r') as file:
                pubspec_content = yaml.safe_load(file)
            version = pubspec_content.get('version', "1.0")
    except Exception as e:
        print(print_utils.warning(f"[{project}] Could not read pubspec.yaml: {e}"))

    # Prepare paths
    new_file_dir = os.path.join(result_path, global_time, project)
    os.makedirs(new_file_dir, exist_ok=True)
    
    extension = 'aab' if build_type == 'appbundle' else 'apk'
    new_file_name = f"{project}-{version}-{build_type}.{extension}"
    new_file = os.path.join(new_file_dir, new_file_name)

    if build_type == 'appbundle':
        app_file = os.path.join(project_path, "build", "app", "outputs", "bundle", "release", "app-release.aab")
    else:
        app_file = os.path.join(project_path, "build", "app", "outputs", "flutter-apk", f"app-{build_type}.apk")

    if os.path.exists(app_file):
        shutil.copy2(app_file, new_file)
        print(print_utils.warning(f"[{project}] Done copy task to: {new_file_dir} | file name: {new_file_name}"))
    else:
        print(print_utils.danger(f"[{project}] Build file not found: {app_file}"))
        return None

    return new_file
