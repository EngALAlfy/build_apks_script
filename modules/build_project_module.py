##############################################
#                                            #
#                 Build module               #
#           Response for operation           #
#           on build project                 #
#                                            #
##############################################
import os
from threading import Thread

from modules import git_module, file_module, flutter_module, send_module, upload_module
from modules.flutter_module import build_debug, build_release, build_appbundle
from utils import print_utils
import bin.constants


def build_project(project, global_time):
    try:
        nice_name = bin.constants.projects.get(project, project)
        print_utils.print_msg_box(f"🚀 Building {nice_name}", color=print_utils.BColors.HEADER)
        
        # clone git project
        git_module.git_clone(project)
        
        # flutter operations
        flutter_module.clean(project)
        flutter_module.pub_get(project)
        flutter_module.intl_generate(project)
        
        # flutter build
        build_types = os.environ.get('BUILD_TYPES', 'release').split(',')
        project_apks = {}

        for build_type in build_types:
            if not build_type: continue
            
            function_name = "build_" + build_type.strip()
            if function_name in globals():
                globals()[function_name](project)
            else:
                print(print_utils.danger(f"Unknown build type: {build_type}"))
                continue

            # copy files to local output and get path
            local_apk_path = file_module.copy_files(project, global_time, build_type)
            if local_apk_path and os.path.exists(local_apk_path):
                project_apks[build_type] = local_apk_path

        print_utils.print_msg_box(f"✅ {project} Build Completed", color=print_utils.BColors.OKGREEN)
        return project_apks

    except Exception as e:
        print(print_utils.danger(f"Failed to build {project}: {e}"))
        return None

