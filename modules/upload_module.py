##############################################
#                                            #
#                Upload module               #
#           Response for operation           #
#           on upload files and folders      #
#                                            #
##############################################
import os
from ftplib import FTP
from mega import Mega
from threading import Thread

from modules import send_module
from utils import print_utils


def upload(project, global_time, apk_path):
    """
    Main upload dispatcher.
    """
    file_urls = {}
    
    # Mega Upload
    if os.getenv('MEGA_ENABLED', 'false').lower() == "true":
        mega_url = upload_to_mega(project, global_time, apk_path)
        if mega_url:
            file_urls['mega'] = mega_url
            
    # FTP Upload
    if os.getenv('FTP_ENABLED', 'false').lower() == "true":
        ftp_url = upload_to_ftp(project, global_time, apk_path)
        if ftp_url:
            file_urls['ftp'] = ftp_url
            
    return file_urls


def upload_to_mega(project, global_time, apk_path):
    try:
        mega = Mega()
        email = os.getenv('MEGA_USERNAME')
        password = os.getenv('MEGA_PASSWORD')
        
        if not email or not password:
            print(print_utils.danger(f"[{project}] MEGA credentials missing"))
            return None

        m = mega.login(email, password)
        dest_filename = f"{project}-{global_time}.apk"
        
        print(print_utils.success(f"[{project}] Starting upload to MEGA ..."))
        print(print_utils.info(f"[{project}] File: {apk_path}"))
        
        file = m.upload(apk_path, dest_filename=dest_filename)
        file_url = m.get_upload_link(file)
        
        print(print_utils.info(f"[{project}] MEGA URL: {file_url}"))
        print(print_utils.warning(f"[{project}] Done MEGA upload"))
        return file_url
    except Exception as e:
        print(print_utils.danger(f"[{project}] MEGA upload failed: {e}"))
        return None


def upload_to_ftp(project, global_time, apk_path):
    try:
        host = os.getenv('FTP_HOST')
        user = os.getenv('FTP_USER')
        password = os.getenv('FTP_PASS')
        remote_path = os.getenv('FTP_PATH', '/')
        
        if not host or not user or not password:
            print(print_utils.danger(f"[{project}] FTP credentials missing"))
            return None

        print(print_utils.success(f"[{project}] Starting upload to FTP ..."))
        
        with FTP(host) as ftp:
            ftp.login(user=user, passwd=password)
            ftp.cwd(remote_path)
            
            filename = f"{project}-{global_time}.apk"
            with open(apk_path, 'rb') as f:
                ftp.storbinary(f'STOR {filename}', f)
                
        ftp_base_url = os.getenv('FTP_BASE_URL', f"ftp://{host}/{remote_path}")
        file_url = f"{ftp_base_url.rstrip('/')}/{filename}"
        
        print(print_utils.info(f"[{project}] FTP URL: {file_url}"))
        print(print_utils.warning(f"[{project}] Done FTP upload"))
        return file_url
    except Exception as e:
        print(print_utils.danger(f"[{project}] FTP upload failed: {e}"))
        return None