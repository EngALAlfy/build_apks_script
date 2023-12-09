import json
import tkinter
import tkinter.messagebox
from tkinter import filedialog
import customtkinter
from bin.constants import version, buildNumber, projects, tasks
from bin.core import build

customtkinter.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        configureTkinter(self=self)
        buildSideBar(self=self)
        browseBar(self=self)
        buildProgressLogs(self=self)
        buildVersionConfiguration(self=self)
        buildGitConfiguration(self=self)
        buildProjectSwitcher(self=self)
        buildTasksCheckBoxes(self=self)

        resetDefaults(self=self)

    def show_logs_command(self):
        if not self.logs_textbox.grid_info():
            self.logs_textbox.grid(row=1, column=1, padx=(20, 0), pady=(20, 0), sticky="nsew")
            self.show_logs_button.configure(text="Hide Logs")
        else:
            self.logs_textbox.grid_remove()
            self.show_logs_button.configure(text="Show Logs")

    def browse_button(self):
        file_path = filedialog.askdirectory(initialdir=self.base_path.get(), title="Select Base Directory")
        if file_path:
            self.base_path.set(file_path)
            save_json({"base_path": self.base_path.get()})

    def browse_button2(self):
        file_path = filedialog.askdirectory(initialdir=self.save_path.get(), title="Select Save Directory")
        if file_path:
            self.save_path.set(file_path)
            save_json({"save_path": self.save_path.get()})


def configureTkinter(self):
    # configure window
    self.title("APK Builder")
    self.geometry(f"{1100}x{580}")

    # configure grid layout (4x4)
    self.grid_columnconfigure(1, weight=1)
    self.grid_columnconfigure((2, 3), weight=0)
    self.grid_rowconfigure((0, 1, 2), weight=1)


def buildSideBar(self):
    # Sidebar with appearance mode
    self.sidebar_frame = customtkinter.CTkFrame(self, width=140, corner_radius=0)
    self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
    self.sidebar_frame.grid_rowconfigure(4, weight=1)
    self.logo_label = customtkinter.CTkLabel(self.sidebar_frame, text="APK Builder",
                                             font=customtkinter.CTkFont(size=20, weight="bold"))
    self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
    self.start_button = customtkinter.CTkButton(self.sidebar_frame, command=lambda: build(**getValues(self)),
                                                text="Start Building")
    self.start_button.grid(row=3, column=0, padx=20, pady=(50, 0))
    self.appearance_mode_label = customtkinter.CTkLabel(self.sidebar_frame, text="Appearance Mode:", anchor="w")
    self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
    self.appearance_mode_optionemenu = customtkinter.CTkOptionMenu(self.sidebar_frame,
                                                                   values=["Light", "Dark", "System"],
                                                                   command=change_appearance_mode_event)
    self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 10))


def browseBar(self):
    # Browse saved directory
    self.base_path = tkinter.StringVar(value=load_json("base_path"))
    self.base_entry = customtkinter.CTkEntry(self, textvariable=self.base_path)
    self.base_entry.grid(row=3, column=1, columnspan=2, padx=(20, 0), pady=5, sticky="nsew")

    self.save_path = tkinter.StringVar(value=load_json("save_path"))
    self.save_entry = customtkinter.CTkEntry(self, textvariable=self.save_path)
    self.save_entry.grid(row=4, column=1, columnspan=2, padx=(20, 0), pady=5, sticky="nsew")

    self.browse_button_1 = customtkinter.CTkButton(master=self, text="Browse Apps Directory",
                                                   command=self.browse_button,
                                                   fg_color="transparent", border_width=2,
                                                   text_color=("gray10", "#DCE4EE"))
    self.browse_button_1.grid(row=3, column=3, padx=(20, 20), pady=5, sticky="nsew")

    self.browse_button_2 = customtkinter.CTkButton(master=self, text="Browse Save Directory",
                                                   command=self.browse_button2,
                                                   fg_color="transparent", border_width=2,
                                                   text_color=("gray10", "#DCE4EE"))
    self.browse_button_2.grid(row=4, column=3, padx=(20, 20), pady=5, sticky="nsew")


def buildProgressLogs(self):
    # Progress Events
    self.slider_progressbar_frame = customtkinter.CTkFrame(self, fg_color="transparent")
    self.slider_progressbar_frame.grid(row=0, column=1, padx=(20, 0), pady=(20, 0), sticky="nsew")
    self.slider_progressbar_frame.grid_columnconfigure(0, weight=1)
    self.slider_progressbar_frame.grid_rowconfigure(4, weight=1)
    self.progress_labels = []
    self.progress_status_labels = []
    self.progressbar_sliders = []
    for idx, (key, value) in enumerate(tasks.items()):
        progress = customtkinter.CTkLabel(self.slider_progressbar_frame, text=f"{value}",
                                          font=customtkinter.CTkFont(size=14, weight="bold"))
        progress.grid(row=idx + 1, column=0, padx=(10, 5), pady=2, sticky="w")
        self.progress_labels.append(progress)
        progress_status = customtkinter.CTkLabel(self.slider_progressbar_frame, text="⏳",
                                                 font=customtkinter.CTkFont(size=14, weight="bold"))
        progress_status.grid(row=idx + 1, column=3, padx=(5, 10), pady=(2, 2), sticky="w")
        self.progress_status_labels.append(progress_status)
        progressbar = customtkinter.CTkProgressBar(self.slider_progressbar_frame)
        self.progressbar_sliders.append(progressbar)
    self.show_logs_button = customtkinter.CTkButton(self.slider_progressbar_frame, command=self.show_logs_command,
                                                    text="Show Logs")
    self.show_logs_button.grid(row=5, column=0, padx=20, pady=(10, 0), sticky="w")

    # Logs
    self.logs_textbox = customtkinter.CTkTextbox(self, width=250)
    self.logs_textbox.tag_add("normal", "1.0", "end")
    self.logs_textbox.tag_add("red", "2.0", "2.9")
    self.logs_textbox.tag_add("green", "3.0", "3.11")
    self.logs_textbox.tag_add("blue", "4.0", "4.10")


def buildVersionConfiguration(self):
    # Configuration frame
    self.configuration_frame = customtkinter.CTkFrame(self, width=250)
    self.configuration_frame.grid(row=0, column=2, padx=(20, 0), pady=(20, 0), sticky="nsew")
    self.configuration_label = customtkinter.CTkLabel(self.configuration_frame, text="Domain",
                                                      font=customtkinter.CTkFont(size=14, weight="bold"))
    self.configuration_label.grid(row=1, column=0, padx=(10, 5), pady=(10, 10), sticky="w")
    self.combobox_1 = customtkinter.CTkComboBox(self.configuration_frame,
                                                values=["beta1", "backend", "aws"])
    self.combobox_1.grid(row=1, column=1, padx=(5, 10), pady=(10, 10), sticky="w")
    self.version_label = customtkinter.CTkLabel(self.configuration_frame, text="App Version",
                                                font=customtkinter.CTkFont(size=14, weight="bold"))
    self.version_label.grid(row=2, column=0, padx=(10, 5), pady=(10, 10), sticky="w")
    self.version_value = customtkinter.StringVar()
    self.version_value.set(f"{version}")
    self.app_version_entry = customtkinter.CTkEntry(self.configuration_frame, textvariable=self.version_value)
    self.app_version_entry.grid(row=2, column=1, padx=(5, 10), pady=(10, 10), sticky="w")
    self.build_label = customtkinter.CTkLabel(self.configuration_frame, text="Build Number",
                                              font=customtkinter.CTkFont(size=14, weight="bold"))
    self.build_label.grid(row=3, column=0, padx=(10, 5), pady=(10, 10), sticky="w")
    self.build_value = customtkinter.StringVar()
    self.build_value.set(f"{buildNumber}")
    self.build_number_entry = customtkinter.CTkEntry(self.configuration_frame, textvariable=self.build_value)
    self.build_number_entry.grid(row=3, column=1, padx=(5, 10), pady=(10, 10), sticky="w")


def buildGitConfiguration(self):
    # Git Branch Radio
    self.radiobutton_frame = customtkinter.CTkFrame(self)
    self.radiobutton_frame.grid(row=0, column=3, padx=(20, 20), pady=(20, 0), sticky="nsew")
    self.radio_var = tkinter.StringVar(value="development")
    self.label_radio_group = customtkinter.CTkLabel(master=self.radiobutton_frame, text="Git Branch:")
    self.label_radio_group.grid(row=0, column=2, columnspan=1, padx=10, pady=10, sticky="w")
    self.radio_button_1 = customtkinter.CTkRadioButton(master=self.radiobutton_frame, variable=self.radio_var,
                                                       value="main", text="main")
    self.radio_button_1.grid(row=1, column=2, pady=10, padx=20, sticky="w")
    self.radio_button_2 = customtkinter.CTkRadioButton(master=self.radiobutton_frame, variable=self.radio_var,
                                                       value="development", text="development")
    self.radio_button_2.grid(row=2, column=2, pady=10, padx=20, sticky="w")


def buildProjectSwitcher(self):
    # Project switches
    self.scrollable_frame = customtkinter.CTkScrollableFrame(self, label_text="Projects")
    self.scrollable_frame.grid(row=1, column=2, padx=(20, 0), pady=(20, 0), sticky="nsew")
    self.scrollable_frame.grid_columnconfigure(0, weight=1)
    self.scrollable_frame_switches = []
    for idx, (key, value) in enumerate(projects.items()):
        switch = customtkinter.CTkSwitch(master=self.scrollable_frame, text=f"{value}", onvalue=f"{key}")
        switch.grid(row=idx, column=0, padx=10, pady=(0, 20), sticky='w')
        switch.select()
        self.scrollable_frame_switches.append(switch)


def buildTasksCheckBoxes(self):
    # Tasks checkboxes
    self.checkbox_slider_frame = customtkinter.CTkFrame(self)
    self.checkbox_slider_frame.grid(row=1, column=3, padx=(20, 20), pady=(20, 0), sticky="nsew")
    self.checkbox_tasks = []
    for idx, (key, value) in enumerate(tasks.items()):
        checkbox = customtkinter.CTkCheckBox(master=self.checkbox_slider_frame, text=f"{value}", onvalue=f"{key}")
        checkbox.grid(row=idx, column=0, pady=(20, 0), padx=20, sticky="w")
        checkbox.select()
        self.checkbox_tasks.append(checkbox)


def resetDefaults(self):
    # set default values
    self.appearance_mode_optionemenu.set("Dark")
    self.combobox_1.set("backend")
    self.logs_textbox.insert("0.0", "Start Logging:\n\n")

    # Define tag configurations for colors
    self.logs_textbox.tag_config("normal", foreground="white")
    self.logs_textbox.tag_config("red", foreground="red")
    self.logs_textbox.tag_config("green", foreground="green")
    self.logs_textbox.tag_config("blue", foreground="blue")


def getValues(self):
    return {
        "self": self,
        "domain": self.combobox_1.get(),
        "version": self.version_value.get(),
        "build_number": self.build_value.get(),
        "projects": list(map(lambda x: x.get(), filter(lambda x: x.get() != 0, self.scrollable_frame_switches))),
        "tasks": list(map(lambda x: x.get(), filter(lambda x: x.get() != 0, self.checkbox_tasks))),
        "git_branch": self.radio_var.get(),
        "base_dir": self.base_path.get(),
        "save_dir": self.save_path.get(),
    }


def change_appearance_mode_event(new_appearance_mode: str):
    customtkinter.set_appearance_mode(new_appearance_mode)


def load_json(key):
    try:
        with open("output.json", 'r') as json_file:
            data = json.load(json_file)
            if key in data:
                return data[key]
            return None
    except FileNotFoundError:
        # If the file doesn't exist, return None
        print(f"File not found")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON in file")
        return None


def save_json(data):
    try:
        with open("output.json", 'r+') as json_file:
            try:
                # Load existing data
                existing_data = json.load(json_file)
            except json.JSONDecodeError:
                # If the file is empty or not valid JSON, initialize with an empty dictionary
                existing_data = {}

            # Append the new data to the existing dictionary
            existing_data.update(data)

            # Move the file cursor to the beginning before writing
            json_file.seek(0)

            # Write the updated data back to the file
            json.dump(existing_data, json_file, indent=2)

            # Truncate the remaining content in case the new data is shorter than the existing
            json_file.truncate()

    except FileNotFoundError:
        # If the file doesn't exist, create a new file with the new data
        with open("output.json", 'w') as json_file:
            json.dump(data, json_file, indent=2)