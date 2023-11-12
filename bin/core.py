import os
from threading import Thread
import subprocess
from tkinter import END

from bin import constants


def build(self, domain, version, build_number, projects, tasks, git_branch, base_dir, save_dir):
    t = Thread(target=lambda: buildProjects(self, base_dir, projects, tasks))
    t.start()


def buildProjects(self, base_dir, projects, tasks):
    for project in projects:
        os.chdir(base_dir+"/"+project)
        changeGitBranch(self)
        performTasks(self, tasks)


def changeGitBranch(self):
    print("changing git branch ...")
    self.logs_textbox.insert(END, subprocess.run("git checkout development", capture_output=True, shell=True, text=True).stdout)
    self.logs_textbox.see(END)


def performTasks(self, tasks):
    for value in tasks:
        idx = list(constants.tasks).index(value)
        eval(value)(self, idx)


def clean(self, idx):
    print("cleaning project ...")
    start_progress(self, idx)
    self.logs_textbox.insert(END, subprocess.run("flutter clean", capture_output=True, shell=True, text=True).stdout)
    self.logs_textbox.see(END)
    stop_progress(self, idx)


def build_debug(self, idx):
    print("build debug apk ...")
    start_progress(self, idx)
    self.logs_textbox.insert(END, subprocess.run("flutter build apk --debug", capture_output=True, shell=True, text=True).stdout)
    self.logs_textbox.see(END)
    stop_progress(self, idx)


def build_release(self, idx):
    print("build release apk ...")
    start_progress(self, idx)
    self.logs_textbox.insert(END, subprocess.run("flutter build apk --release", capture_output=True, shell=True, text=True).stdout)
    self.logs_textbox.see(END)
    stop_progress(self, idx)


def build_aap(self, idx):
    print("build release app bundle ...")
    start_progress(self, idx)
    self.logs_textbox.insert(END, subprocess.run("flutter build appbundle", capture_output=True, shell=True, text=True).stdout)
    self.logs_textbox.see(END)
    stop_progress(self, idx)


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