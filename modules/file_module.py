##############################################
#                                            #
#                 File module                #
#           Response for operation           #
#           on build files and folders       #
#                                            #
##############################################
import json

from utils import print_utils


def change_domain(project, domain):
    print(print_utils.success(f"[{project}] Change domain to [{domain}]"))
    try:
        # Load the JSON file
        with open('assets/cfg/configurations.json', 'r') as file:
            data = json.load(file)

        # Modify the value of the "url" key
        data['base_url'] = f'https://{domain}.hurryapps.com/'
        data['api_base_url'] = f'https://{domain}.hurryapps.com/api/'

        # Save the modified data back to the file
        with open('assets/cfg/configurations.json', 'w') as file:
            json.dump(data, file, indent=4)

    except FileNotFoundError:
        print(print_utils.danger(f"[{project}] Cannot find configurations file ..."))
