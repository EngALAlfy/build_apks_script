##############################################
#                                            #
#                 Build module               #
#           Response for operation           #
#           on build project                 #
#                                            #
##############################################
from threading import Thread

from modules import git_module, file_module, flutter_module, upload_module, send_module
from utils import print_utils


def build_project(project, domain , global_time):
    print_utils.print_msg_box(f"\n [{project}] \n Start building APKs for {project} \n",
                              color=print_utils.BColors.INFO, indent=10)
    # clone git project
    git_module.git_clone(project)
    # change domain of build
    # file_module.change_domain(project, domain)
    # flutter clean
    flutter_module.clean(project)
    # flutter pub get
    flutter_module.pub_get(project)
    # flutter intl generate
    flutter_module.intl_generate(project)
    # flutter build debug
    flutter_module.build_debug(project)
    # flutter build release
    flutter_module.build_release(project)
    # flutter build appbundle
    # flutter_module.build_appbundle(project)
    # copy files
    new_debug_file = file_module.copy_files(project, domain, global_time)
    # upload builds to mega
    file_url = upload_module.upload_to_mega(project, domain, global_time)
    if file_url is None:
        file_url = new_debug_file
    # send notify top discord
    send_module.send_to_discord(project,domain, file_url, global_time)

