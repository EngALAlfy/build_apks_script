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


def build_project(project, global_time):
    try:
        print_utils.print_msg_box(f"🚀 Building {project}", color=print_utils.BColors.HEADER)
        
        # clone git project
        git_module.git_clone(project)
        
        # flutter operations
        flutter_module.clean(project)
        flutter_module.pub_get(project)
        flutter_module.intl_generate(project)
        
        # flutter build
        build_types = os.environ.get('BUILD_TYPES', 'release').split(',')
        all_file_urls = {}

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
                # upload builds (Mega, FTP, etc.)
                uploaded_urls = upload_module.upload(project, global_time, local_apk_path)
                all_file_urls.update(uploaded_urls)
                
                # If no cloud URL, use local path as fallback
                if not all_file_urls:
                    all_file_urls['local'] = local_apk_path

        # Send notifications
        if all_file_urls:
            send_module.send_to_discord(project, all_file_urls, global_time)
            send_module.send_to_email(project, all_file_urls, global_time)
            
        print_utils.print_msg_box(f"✅ {project} Completed", color=print_utils.BColors.OKGREEN)

    except Exception as e:
        print(print_utils.danger(f"Failed to build {project}: {e}"))

