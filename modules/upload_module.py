"""Optional distribution adapters. Local building does not require cloud SDKs."""
import os
from pathlib import Path
from ftplib import FTP
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from utils import print_utils
from modules.process_runner import check_cancelled, BuildCancelled
import bin.constants


def mega_client():
    # mega.py's legacy tenacity dependency still imports asyncio.coroutine.
    import asyncio
    import types
    if not hasattr(asyncio, 'coroutine'):
        asyncio.coroutine = types.coroutine
    from mega import Mega
    return Mega()


def mass_upload(all_projects_apks, global_time):
    """
    Uploads all built APKs in parallel.
    all_projects_apks: List of tuples (project_name, {build_type: local_path})
    """
    print_utils.print_msg_box("Starting cloud uploads (MEGA & FTP)", color=print_utils.BColors.HEADER)
    
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
        
        for future in as_completed(futures):
            try:
                project, build_type, urls, metadata = future.result()
                if project not in results: results[project] = {}
                results[project][build_type] = {"urls": urls, "metadata": metadata}
            except BuildCancelled:
                raise
            except Exception as e:
                print(f"\n{print_utils.danger(f'Critical upload error: {e}')}")

    return results


def process_single_upload(project, build_type, apk_path, global_time):
    check_cancelled()
    
    urls = {}
    metadata = {}
    
    # Mega Upload
    if os.getenv('MEGA_ENABLED', 'false').lower() == "true":
        mega_result = upload_to_mega(project, build_type, global_time, apk_path)
        if mega_result:
            urls['mega'] = mega_result['url']
            metadata['mega_handle'] = mega_result['handle']
            
    check_cancelled()
    # FTP Upload
    if os.getenv('FTP_ENABLED', 'false').lower() == "true":
        ftp_url = upload_to_ftp(project, build_type, global_time, apk_path)
        if ftp_url:
            urls['ftp'] = ftp_url
            
    return project, build_type, urls, metadata


def upload_to_mega(project, build_type, global_time, apk_path):
    try:
        mega = mega_client()
        email = os.getenv('MEGA_USERNAME')
        password = os.getenv('MEGA_PASSWORD')
        
        if not email or not password:
            return None

        m = mega.login(email, password)
        dest_filename = f"{project}-{build_type}-{global_time}{Path(apk_path).suffix}"
        
        file = m.upload(apk_path, dest_filename=dest_filename)
        file_url = m.get_upload_link(file)
        
        # Extract handle for deletion later
        handle = None
        if isinstance(file, dict) and 'f' in file and len(file['f']) > 0:
            handle = file['f'][0].get('h')
        
        return {"url": file_url, "handle": handle}

    except BuildCancelled:
        raise
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
            check_cancelled()
            uploaded += len(chunk)
            # Update console every 0.2 seconds to avoid flooding
            if time.time() - last_update > 0.2 or uploaded == file_size:
                percent = (uploaded / max(file_size, 1)) * 100
                nice_name = bin.constants.projects.get(project, project)
                print(f"  > [{nice_name}][{build_type}] FTP Uploading: {percent:.1f}%", end='\r', flush=True)
                last_update = time.time()

        with FTP(host, timeout=30) as ftp:
            ftp.login(user=user, passwd=password)
            ftp.cwd(remote_path)
            
            filename = f"{project}-{build_type}-{global_time}{Path(apk_path).suffix}"
            with open(apk_path, 'rb') as f:
                ftp.storbinary(f'STOR {filename}', f, callback=callback)
                
        print() # New line when done
        ftp_base_url = os.getenv('FTP_BASE_URL', f"ftp://{host}/{remote_path}")
        file_url = f"{ftp_base_url.rstrip('/')}/{filename}"
        return file_url
    except BuildCancelled:
        raise
    except Exception as e:
        print(f"\n{print_utils.danger(f'[{project}][{build_type}] FTP upload failed: {e}')}")
        return None

def delete_from_mega(handle):
    try:
        mega = mega_client()
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
        with FTP(host, timeout=30) as ftp:
            ftp.login(user=user, passwd=password)
            ftp.cwd(remote_path)
            ftp.delete(filename)
        return True
    except Exception as e:
        print(f"Failed to delete from FTP: {e}")
        return False
