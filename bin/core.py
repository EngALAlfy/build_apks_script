import os
from threading import Thread
from time import sleep

from bin import constants


def build(self, domain, version, buildNumber, projects, tasks, gitBranch):
    print(domain, version, buildNumber, projects, tasks, gitBranch, sep="\n")
    t = Thread(target=lambda: performTasks(self, tasks))
    t.start()
    # for value in tasks:
        # eval(value)(self)


def performTasks(self, tasks):
    for value in tasks:
        idx = list(constants.tasks).index(value)
        eval(value)(self, idx)
    return


def clean(self, idx):
    print("cleaning project ...")
    start_progress(self, idx)
    sleep(3)
    stop_progress(self, idx)


def build_debug(self, idx):
    print("build debug apk ...")
    start_progress(self, idx)
    sleep(3)
    stop_progress(self, idx)


def build_release(self, idx):
    print("build release apk ...")
    start_progress(self, idx)
    sleep(3)
    stop_progress(self, idx)


def build_aap(self, idx):
    print("build release app bundle ...")
    start_progress(self, idx)
    sleep(3)
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