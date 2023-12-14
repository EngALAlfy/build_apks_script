##############################################
#                                            #
#               Flutter module               #
#           Response for operation           #
#           on build flutter projects        #
#                                            #
##############################################
import os

from utils import print_utils, commands_utils


def clean(project):
    print(print_utils.success(f"[{project}] flutter clean ..."))
    os.system(commands_utils.FLUTTER_CLEAN_COMMAND)
    print(print_utils.warning(f"[{project}] Done clean task"))


def pub_get(project):
    print(print_utils.success(f"[{project}] flutter pub get ..."))
    os.system(commands_utils.FLUTTER_PUB_GET_COMMAND)
    print(print_utils.warning(f"[{project}] Done pub get task"))


def intl_generate(project):
    print(print_utils.success(f"[{project}] flutter intl generate ..."))
    os.system(commands_utils.FLUTTER_INTL_GENERATE_COMMAND)
    print(print_utils.warning(f"[{project}] Done intl generate task"))


def build_debug(project):
    print(print_utils.success(f"[{project}] flutter build debug ..."))
    os.system(commands_utils.FLUTTER_BUILD_DEBUG_COMMAND)
    print(print_utils.warning(f"[{project}] Done build debug task"))


def build_release(project):
    print(print_utils.success(f"[{project}] flutter build release ..."))
    os.system(commands_utils.FLUTTER_BUILD_RELEASE_COMMAND)
    print(print_utils.warning(f"[{project}] Done  build release task"))


def build_appbundle(project):
    print(print_utils.success(f"[{project}] flutter build appbundle ..."))
    os.system(commands_utils.FLUTTER_BUILD_APPBUNDLE_COMMAND)
    print(print_utils.warning(f"[{project}] Done build appbundle task"))