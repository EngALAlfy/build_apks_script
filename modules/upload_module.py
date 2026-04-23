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
import mega.mega
import builtins
from concurrent.futures import ThreadPoolExecutor
import time
import threading

from modules import send_module
from utils import print_utils
import bin.constants

# Thread-local storage to pass context to the monkey-patched open()
thread_local = threading.local()

class ProgressFile:
    def __init__(self, file_path, project, build_type):
        self.file_path = file_path
        self.project = project
        self.build_type = build_type
        self.size = os.path.getsize(file_path)
        self.read_bytes = 0
        self.last_update = 0
        self.fd = open(file_path, 'rb')

    def read(self, size=-1):
        data = self.fd.read(size)
        if data:
            self.read_bytes += len(data)
            
            # Only update console every 0.2 seconds to avoid flooding
            if time.time() - self.last_update > 0.2 or self.read_bytes == self.size:
                percent = (self.read_bytes / self.size) * 100
                nice_name = bin.constants.projects.get(self.project, self.project)
                print(f"  ➜ [{nice_name}][{self.build_type}] MEGA Uploading: {percent:.1f}%", end='\r', flush=True)
                self.last_update = time.time()
                if self.read_bytes == self.size:
                    print() # New line when done
        return data

    def __iter__(self):
        return self.fd.__iter__()

    def __next__(self):
        return self.fd.__next__()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.fd.close()

# Monkey-patch mega.mega.open to use ProgressFile
original_mega_open = getattr(mega.mega, 'open', builtins.open)

def patched_mega_open(file, mode='r', *args, **kwargs):
    if mode == 'rb' and hasattr(thread_local, 'project'):
        return ProgressFile(file, thread_local.project, thread_local.build_type)
    return original_mega_open(file, mode, *args, **kwargs)

mega.mega.open = patched_mega_open


def mass_upload(all_projects_apks, global_time):
    """
    Uploads all built APKs in parallel.
    all_projects_apks: List of tuples (project_name, {build_type: local_path})
    """
    print_utils.print_msg_box("☁️ Starting Cloud Uploads (MEGA & FTP)", color=print_utils.BColors.HEADER)
    
    upload_tasks = []
    for project, apks in all_projects_apks:
        for build_type, path in apks.items():
            upload_tasks.append((project, build_type, path))

    results = {} # {project: {build_type: {mega: url, ftp: url}}}

    # Limit parallel uploads to 3 to avoid hitting MEGA rate limits or bandwidth saturation
    with ThreadPoolExecutor(max_workers=min(len(upload_tasks) or 1, 3)) as executor:
        futures = []
        for project, build_type, path in upload_tasks:
            futures.append(executor.submit(process_single_upload, project, build_type, path, global_time))
        
        for future in futures:
            try:
                project, build_type, urls, metadata = future.result()
                if project not in results: results[project] = {}
                results[project][build_type] = {"urls": urls, "metadata": metadata}
            except Exception as e:
                print(f"\n{print_utils.danger(f'Critical upload error: {e}')}")

    return results


def process_single_upload(project, build_type, apk_path, global_time):
    # Set thread-local context for the patched open()
    thread_local.project = project
    thread_local.build_type = build_type
    
    urls = {}
    metadata = {}
    
    # Mega Upload
    if os.getenv('MEGA_ENABLED', 'false').lower() == "true":
        mega_result = upload_to_mega(project, build_type, global_time, apk_path)
        if mega_result:
            urls['mega'] = mega_result['url']
            metadata['mega_handle'] = mega_result['handle']
            
    # FTP Upload
    if os.getenv('FTP_ENABLED', 'false').lower() == "true":
        ftp_url = upload_to_ftp(project, build_type, global_time, apk_path)
        if ftp_url:
            urls['ftp'] = ftp_url
            
    return project, build_type, urls, metadata


def upload_to_mega(project, build_type, global_time, apk_path):
    try:
        mega = Mega()
        email = os.getenv('MEGA_USERNAME')
        password = os.getenv('MEGA_PASSWORD')
        
        if not email or not password:
            return None

        m = mega.login(email, password)
        dest_filename = f"{project}-{build_type}-{global_time}.apk"
        
        # This will trigger patched_mega_open
        file = m.upload(apk_path, dest_filename=dest_filename)
        file_url = m.get_upload_link(file)
        
        # Extract handle for deletion later
        handle = None
        if isinstance(file, dict) and 'f' in file and len(file['f']) > 0:
            handle = file['f'][0].get('h')
        
        return {"url": file_url, "handle": handle}

    except Exception as e:
        print(f"\n{print_utils.danger(f'[{project}][{build_type}] MEGA upload failed: {e}')}")
        return None


def upload_to_ftp(project, build_type, global_time, apk_path):
    try:
        host = os.getenv('FTP_HOST')
        user = os.getenv('FTP_USER')
        password = os.getenv('FTP_PASS')
        remote_path = os.getenv('FTP_PATH', '/')
        
        if not host or not user or not password:
            return None

        file_size = os.path.getsize(apk_path)
        uploaded = 0
        last_update = 0
        
        def callback(chunk):
            nonlocal uploaded, last_update
            uploaded += len(chunk)
            # Update console every 0.2 seconds to avoid flooding
            if time.time() - last_update > 0.2 or uploaded == file_size:
                percent = (uploaded / file_size) * 100
                nice_name = bin.constants.projects.get(project, project)
                print(f"  ➜ [{nice_name}][{build_type}] FTP Uploading: {percent:.1f}%", end='\r', flush=True)
                last_update = time.time()

        with FTP(host) as ftp:
            ftp.login(user=user, passwd=password)
            ftp.cwd(remote_path)
            
            filename = f"{project}-{build_type}-{global_time}.apk"
            with open(apk_path, 'rb') as f:
                ftp.storbinary(f'STOR {filename}', f, callback=callback)
                
        print() # New line when done
        ftp_base_url = os.getenv('FTP_BASE_URL', f"ftp://{host}/{remote_path}")
        file_url = f"{ftp_base_url.rstrip('/')}/{filename}"
        return file_url
    except Exception as e:
        print(f"\n{print_utils.danger(f'[{project}][{build_type}] FTP upload failed: {e}')}")
        return None

def delete_from_mega(handle):
    try:
        mega = Mega()
        m = mega.login(os.getenv('MEGA_USERNAME'), os.getenv('MEGA_PASSWORD'))
        m.destroy(handle)
        return True
    except Exception as e:
        print(f"Failed to delete from MEGA: {e}")
        return False

def delete_from_ftp(filename):
    try:
        host = os.getenv('FTP_HOST')
        user = os.getenv('FTP_USER')
        password = os.getenv('FTP_PASS')
        remote_path = os.getenv('FTP_PATH', '/')
        with FTP(host) as ftp:
            ftp.login(user=user, passwd=password)
            ftp.cwd(remote_path)
            ftp.delete(filename)
        return True
    except Exception as e:
        print(f"Failed to delete from FTP: {e}")
        return False
