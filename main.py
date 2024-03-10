import os
import sys
from datetime import datetime

from dotenv import load_dotenv

from modules import build_project_module, send_module
from utils import print_utils

load_dotenv()


def start_build_projects():
    projects = os.getenv('PROJECTS_REPOS')
    supported_domains = os.getenv('SUPPORTED_DOMAINS')
    default_domain = os.getenv('DEFAULT_DOMAIN')
    domain = get_arg_value("--domain", default_domain)

    # Split the string into an array using the comma as a delimiter
    if projects:
        projects = projects.split(',')

    if supported_domains:
        supported_domains = supported_domains.split(',')

    if domain not in supported_domains:
        print(print_utils.danger(f"Domain [{domain}] not in supported domains"))
        exit(0)

    global_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    for project in projects:
        build_project_module.build_project(project, domain, global_time)


def get_arg_value(option, default=None):
    if option in sys.argv[1:]:
        index_of_option = sys.argv.index(option)
        # Get the value following the option
        if index_of_option + 1 < len(sys.argv):
            option_value = sys.argv[index_of_option + 1]
            if option_value is None:
                option_value = default
            return option_value
        else:
            return default
    else:
        return default


if __name__ == "__main__":
    try:
        start_build_projects()
    except KeyboardInterrupt:
        print(print_utils.danger(f"Script ended manually with CTRL + C"))
        raise SystemExit
    except Exception as err:
        print(print_utils.danger(f"Error occur : {err}"))
