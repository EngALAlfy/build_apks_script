##############################################
#                                            #
#                 Build module               #
#           Response for operation           #
#           on build project                 #
#                                            #
##############################################
from threading import Thread

from modules import git_module, file_module, flutter_module
from utils import print_utils


def build_project_thread(project, domain):
    print_utils.print_msg_box(f"\n [{project}] \n Start building APKs for {project} \n",
                              color=print_utils.BColors.INFO, indent=10)
    # clone git project
    git_module.git_clone(project)
    # change domain of build
    file_module.change_domain(project, domain)
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
    flutter_module.build_appbundle(project)


def build(project, domain):
    t = Thread(target=lambda: build_project_thread(project, domain))
    t.start()