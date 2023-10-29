import tkinter
import tkinter.messagebox
from tkinter import filedialog

import customtkinter

customtkinter.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

# Define the projects names
projects = {
    "hurryApp": "HurryApp",
    "restaurant_manager": "Restaurant Manager",
    "BranchManager": "Branch Manager",
    "delivery_captin": "Captain App",
}

version = "0.0.46"
buildNumber = 46


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # configure window
        self.title("APK Builder")
        self.geometry(f"{1100}x{580}")

        # configure grid layout (4x4)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure((2, 3), weight=0)
        self.grid_rowconfigure((0, 1, 2), weight=1)

        # Sidebar with appearance mode
        self.sidebar_frame = customtkinter.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        self.logo_label = customtkinter.CTkLabel(self.sidebar_frame, text="APK Builder",
                                                 font=customtkinter.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        self.appearance_mode_label = customtkinter.CTkLabel(self.sidebar_frame, text="Appearance Mode:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = customtkinter.CTkOptionMenu(self.sidebar_frame,
                                                                       values=["Light", "Dark", "System"],
                                                                       command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 10))

        # Browse saved directory
        self.folder_path = tkinter.StringVar()
        self.entry = customtkinter.CTkEntry(self, placeholder_text="Save Directory", textvariable=self.folder_path)
        self.entry.grid(row=3, column=1, columnspan=2, padx=(20, 0), pady=(20, 20), sticky="nsew")
        self.main_button_1 = customtkinter.CTkButton(master=self, text="Browse", command=self.browse_button,
                                                     fg_color="transparent", border_width=2,
                                                     text_color=("gray10", "#DCE4EE"))
        self.main_button_1.grid(row=3, column=3, padx=(20, 20), pady=(20, 20), sticky="nsew")

        # Progress Events
        self.slider_progressbar_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.slider_progressbar_frame.grid(row=0, column=1, padx=(20, 0), pady=(20, 0), sticky="nsew")
        self.slider_progressbar_frame.grid_columnconfigure(0, weight=1)
        self.slider_progressbar_frame.grid_rowconfigure(4, weight=1)
        self.progressbar_label_1 = customtkinter.CTkLabel(self.slider_progressbar_frame, text="Flutter pub get",
                                                          font=customtkinter.CTkFont(size=14, weight="bold"))
        self.progressbar_label_1.grid(row=1, column=0, padx=(10, 5), pady=(2, 2), sticky="w")
        self.progressbar_status_1 = customtkinter.CTkLabel(self.slider_progressbar_frame, text="✅",
                                                           font=customtkinter.CTkFont(size=14, weight="bold"))
        self.progressbar_status_1.grid(row=1, column=2, padx=(5, 10), pady=(2, 2), sticky="w")
        self.progressbar_label_2 = customtkinter.CTkLabel(self.slider_progressbar_frame, text="Flutter build apk",
                                                          font=customtkinter.CTkFont(size=14, weight="bold"))
        self.progressbar_label_2.grid(row=2, column=0, padx=(10, 5), pady=(2, 2), sticky="w")
        self.progressbar_2 = customtkinter.CTkProgressBar(self.slider_progressbar_frame)
        self.progressbar_2.grid(row=2, column=2, padx=(5, 10), pady=(2, 2), sticky="w")
        self.progressbar_label_3 = customtkinter.CTkLabel(self.slider_progressbar_frame, text="Flutter build appbundle",
                                                          font=customtkinter.CTkFont(size=14, weight="bold"))
        self.progressbar_label_3.grid(row=3, column=0, padx=(10, 5), pady=(2, 2), sticky="w")
        self.progressbar_status_3 = customtkinter.CTkLabel(self.slider_progressbar_frame, text="⏳",
                                                           font=customtkinter.CTkFont(size=14, weight="bold"))
        self.progressbar_status_3.grid(row=3, column=2, padx=(5, 10), pady=(2, 2), sticky="w")
        self.show_logs_button = customtkinter.CTkButton(self.slider_progressbar_frame, command=self.show_logs_command,
                                                        text="Show Logs")
        self.show_logs_button.grid(row=4, column=0, padx=20, pady=(10, 0), sticky="w")

        # Logs
        self.logs_textbox = customtkinter.CTkTextbox(self, width=250)
        # self.logs_textbox.grid(row=1, column=1, padx=(20, 0), pady=(20, 0), sticky="nsew")

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

        # Git Branch Radio
        self.radiobutton_frame = customtkinter.CTkFrame(self)
        self.radiobutton_frame.grid(row=0, column=3, padx=(20, 20), pady=(20, 0), sticky="nsew")
        self.radio_var = tkinter.IntVar(value=1)
        self.label_radio_group = customtkinter.CTkLabel(master=self.radiobutton_frame, text="Git Branch:")
        self.label_radio_group.grid(row=0, column=2, columnspan=1, padx=10, pady=10, sticky="w")
        self.radio_button_1 = customtkinter.CTkRadioButton(master=self.radiobutton_frame, variable=self.radio_var,
                                                           value=0, text="main")
        self.radio_button_1.grid(row=1, column=2, pady=10, padx=20, sticky="w")
        self.radio_button_2 = customtkinter.CTkRadioButton(master=self.radiobutton_frame, variable=self.radio_var,
                                                           value=1, text="development")
        self.radio_button_2.grid(row=2, column=2, pady=10, padx=20, sticky="w")

        # Project switches
        self.scrollable_frame = customtkinter.CTkScrollableFrame(self, label_text="Projects")
        self.scrollable_frame.grid(row=1, column=2, padx=(20, 0), pady=(20, 0), sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        self.scrollable_frame_switches = []
        for idx, (key, value) in enumerate(projects.items()):
            switch = customtkinter.CTkSwitch(master=self.scrollable_frame, text=f"{value}")
            switch.grid(row=idx, column=0, padx=10, pady=(0, 20), sticky='w')
            switch.select()
            self.scrollable_frame_switches.append(switch)

        # Tasks checkboxes
        self.checkbox_slider_frame = customtkinter.CTkFrame(self)
        self.checkbox_slider_frame.grid(row=1, column=3, padx=(20, 20), pady=(20, 0), sticky="nsew")
        self.checkbox_1 = customtkinter.CTkCheckBox(master=self.checkbox_slider_frame, text="Clean")
        self.checkbox_1.grid(row=1, column=0, pady=(20, 0), padx=20, sticky="w")
        self.checkbox_2 = customtkinter.CTkCheckBox(master=self.checkbox_slider_frame, text="Build Debug")
        self.checkbox_2.grid(row=2, column=0, pady=(20, 0), padx=20, sticky="w")
        self.checkbox_3 = customtkinter.CTkCheckBox(master=self.checkbox_slider_frame, text="Build Release")
        self.checkbox_3.grid(row=3, column=0, pady=(20, 0), padx=20, sticky="w")
        self.checkbox_4 = customtkinter.CTkCheckBox(master=self.checkbox_slider_frame, text="Build App Bundle")
        self.checkbox_4.grid(row=4, column=0, pady=(20, 0), padx=20, sticky="w")

        # set default values
        self.checkbox_1.select()
        self.checkbox_2.select()
        self.checkbox_3.select()
        self.checkbox_4.select()
        self.appearance_mode_optionemenu.set("Dark")
        self.combobox_1.set("backend")
        self.progressbar_2.configure(mode="indeterminnate")
        self.progressbar_2.start()
        self.logs_textbox.insert("0.0", "Logs:\n\n" + "Flutter pub get ...\nFlutter build apk ...\n")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        customtkinter.set_appearance_mode(new_appearance_mode)

    def show_logs_command(self):
        if not self.logs_textbox.grid_info():
            self.logs_textbox.grid(row=1, column=1, padx=(20, 0), pady=(20, 0), sticky="nsew")
            self.show_logs_button.configure(text="Hide Logs")
        else:
            self.logs_textbox.grid_remove()
            self.show_logs_button.configure(text="Show Logs")

    def browse_button(self):
        # Allow user to select a directory and store it in global var
        # called folder_path
        filename = filedialog.askdirectory()
        self.folder_path.set(filename)
        print(filename)


if __name__ == "__main__":
    app = App()
    app.mainloop()
