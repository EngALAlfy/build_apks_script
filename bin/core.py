import json
import os
import shutil
import yaml
from threading import Thread
import subprocess
from tkinter import END
from datetime import datetime

from bin import constants


def build(self, domain, version, build_number, projects, tasks, git_branch, base_dir, save_dir):
    t = Thread(target=lambda: buildProjects(self, base_dir, projects, tasks, git_branch, domain, save_dir))
    t.start()


def buildProjects(self, base_dir, projects, tasks, git_branch, domain, save_dir):
    for project in projects:
        save_dir = f'{save_dir}/{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}/{project}/{domain}'
        os.chdir(f'{base_dir}/{project}')
        changeGitBranch(self, git_branch)
        changeDomain(self, domain)
        performTasks(self, tasks)
        saveBuilds(self, f'{base_dir}/{project}', save_dir)
        renameBuilds(self, project, save_dir)


def changeGitBranch(self, git_branch):
    self.logs_textbox.insert(END, f"\nUpdate GIT data from branch {git_branch} ...\n", "blue")
    self.logs_textbox.see(END)

    self.logs_textbox.insert(END, subprocess.run(f"git pull origin {git_branch}:{git_branch}", capture_output=True, shell=True, text=True).stdout, "normal")
    self.logs_textbox.see(END)

    self.logs_textbox.insert(END, f"\nNow on {git_branch} branch.\n", "green")
    self.logs_textbox.see(END)


def changeDomain(self, domain):
    self.logs_textbox.insert(END, f"\nChanging domain to {domain} ...\n", "blue")
    self.logs_textbox.see(END)

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

        self.logs_textbox.insert(END, f"\nNow working on {domain} domain ...\n", "green")
        self.logs_textbox.see(END)
    except FileNotFoundError:
        self.logs_textbox.insert(END, f"\nCannot find configurations file ...\n", "red")
        self.logs_textbox.see(END)


def performTasks(self, tasks):
    for value in tasks:
        idx = list(constants.tasks).index(value)
        eval(value)(self, idx)


def clean(self, idx):
    self.logs_textbox.insert(END, "\nCleaning project ...\n", "blue")
    self.logs_textbox.see(END)

    start_progress(self, idx)
    self.logs_textbox.insert(END, subprocess.run("flutter clean", capture_output=True, shell=True, text=True).stdout, "normal")
    self.logs_textbox.see(END)
    stop_progress(self, idx)

    self.logs_textbox.insert(END, "\nCleaning project Success.\n", "green")
    self.logs_textbox.see(END)


def build_debug(self, idx):
    self.logs_textbox.insert(END, "\nBuild debug apk ...\n", "blue")
    self.logs_textbox.see(END)

    start_progress(self, idx)
    self.logs_textbox.insert(END, subprocess.run("flutter build apk --debug", capture_output=True, shell=True, text=True).stdout, "normal")
    self.logs_textbox.see(END)
    stop_progress(self, idx)

    self.logs_textbox.insert(END, "\nDebug apk build successfully.\n", "green")
    self.logs_textbox.see(END)


def build_release(self, idx):
    self.logs_textbox.insert(END, "\nBuild release apk ...\n", "blue")
    self.logs_textbox.see(END)

    start_progress(self, idx)
    self.logs_textbox.insert(END, subprocess.run("flutter build apk --release", capture_output=True, shell=True, text=True).stdout, "normal")
    self.logs_textbox.see(END)
    stop_progress(self, idx)

    self.logs_textbox.insert(END, "\nRelease apk build successfully.\n", "green")
    self.logs_textbox.see(END)


def build_aap(self, idx):
    self.logs_textbox.insert(END, "\nBuild release app bundle ...\n", "blue")
    self.logs_textbox.see(END)

    start_progress(self, idx)
    self.logs_textbox.insert(END, subprocess.run("flutter build appbundle", capture_output=True, shell=True, text=True).stdout, "normal")
    self.logs_textbox.see(END)
    stop_progress(self, idx)

    self.logs_textbox.insert(END, "\nRelease app bundle build successfully.\n", "green")
    self.logs_textbox.see(END)


def saveBuilds(self, base_dir, save_dir):
    self.logs_textbox.insert(END, "\nSave Build Files ...\n", "blue")
    self.logs_textbox.see(END)

    try:
        # create build dir
        os.makedirs(save_dir, 511, True)

        # copy apk debug
        shutil.copy2(f'{base_dir}/build/app/outputs/flutter-apk/app-debug.apk', save_dir)

        # copy apk release
        shutil.copy2(f'{base_dir}/build/app/outputs/flutter-apk/app-release.apk', save_dir)

        # copy appbundle
        shutil.copy2(f'{base_dir}/build/app/outputs/bundle/release/app-release.aab', save_dir)

        self.logs_textbox.insert(END, "\nBuild files saved successfully.\n", "green")
        self.logs_textbox.see(END)
    except FileNotFoundError:
        self.logs_textbox.insert(END, f"\nCannot find build directory ...\n", "red")
        self.logs_textbox.see(END)


def renameBuilds(self, project, save_dir):
    self.logs_textbox.insert(END, "\nRename Build Files ...\n", "blue")
    self.logs_textbox.see(END)

    version = ""
    try:
        with open('pubspec.yaml', 'r') as file:
            pubspec_content = yaml.safe_load(file)

        version = pubspec_content.get('version')
    except FileNotFoundError:
        self.logs_textbox.insert(END, f"\nCannot find yaml file ...\n", "red")
        self.logs_textbox.see(END)

    try:
        if version:
            os.rename(f"{save_dir}/app-debug.apk", f"{save_dir}/{project}_{version}_debug.apk")

            os.rename(f"{save_dir}/app-release.apk", f"{save_dir}/{project}_{version}_release.apk")

            os.rename(f"{save_dir}/app-release.aab", f"{save_dir}/{project}_{version}_release.aab")

            self.logs_textbox.insert(END, "\nRename Build Files Done.\n", "green")
            self.logs_textbox.see(END)
        else:
            self.logs_textbox.insert(END, "\nVersion not found.\n", "red")
            self.logs_textbox.see(END)
    except FileNotFoundError:
        self.logs_textbox.insert(END, f"\nCannot find build directory ...\n", "red")
        self.logs_textbox.see(END)


def start_progress(self, idx):
    self.progress_status_labels[idx].grid_remove()
    self.progressbar_sliders[idx].grid(row=idx+1, column=2, padx=(5, 10), pady=(2, 2), sticky="w")
    self.progressbar_sliders[idx].configure(mode="indeterminnate")
    self.progressbar_sliders[idx].start()


def stop_progress(self, idx):
    self.progress_status_labels[idx].configure(text="✅")
    self.progress_status_labels[idx].grid(row=idx+1, column=3, padx=(5, 10), pady=(2, 2), sticky="w")
    self.progressbar_sliders[idx].stop()
    self.progressbar_sliders[idx].grid_remove()