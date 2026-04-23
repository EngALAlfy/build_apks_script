import os
import sys
import tkinter
import tkinter.messagebox
from tkinter import filedialog
from datetime import datetime
import customtkinter
import bin.constants
from utils import print_utils
from modules import build_project_module
import dotenv
from threading import Thread
import re
from utils import notification_utils

customtkinter.set_appearance_mode("Dark")
customtkinter.set_default_color_theme("blue")

class StdoutRedirector:
    def __init__(self, textbox):
        self.textbox = textbox

    def write(self, message):
        # Remove ANSI escape sequences for cleaner UI display
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_message = ansi_escape.sub('', message)
        
        self.textbox.configure(state="normal")
        self.textbox.insert(tkinter.END, clean_message)
        self.textbox.see(tkinter.END)
        self.textbox.configure(state="disabled")

    def flush(self):
        pass

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # Window configuration
        self.title("APK Professional Builder v2.0")
        self.geometry("1400x700")

        # Layout configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Initialize variables
        self.init_variables()

        # Build UI
        self.create_sidebar()
        self.create_main_content()
        
        # Load defaults
        self.load_settings()

    def init_variables(self):
        self.git_workspace = tkinter.StringVar(value=os.getenv('GIT_WORKSPACE', ''))
        self.result_workspace = tkinter.StringVar(value=os.getenv('RESULT_WORKSPACE', ''))
        self.git_branch = tkinter.StringVar(value=os.getenv('GIT_BRANCH', 'main'))
        
        # Distribution Toggles
        self.mega_enabled = tkinter.BooleanVar(value=os.getenv('MEGA_ENABLED', 'false').lower() == "true")
        self.ftp_enabled = tkinter.BooleanVar(value=os.getenv('FTP_ENABLED', 'false').lower() == "true")
        self.discord_enabled = tkinter.BooleanVar(value=os.getenv('DISCORD_ENABLED', 'false').lower() == "true")
        self.email_enabled = tkinter.BooleanVar(value=os.getenv('EMAIL_ENABLED', 'false').lower() == "true")

    def create_sidebar(self):
        self.sidebar = customtkinter.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        self.logo_label = customtkinter.CTkLabel(self.sidebar, text="APK BUILDER", font=customtkinter.CTkFont(size=22, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.status_indicator = customtkinter.CTkLabel(self.sidebar, text="● IDLE", text_color="gray", font=customtkinter.CTkFont(size=12))
        self.status_indicator.grid(row=1, column=0, padx=20, pady=(0, 20))

        self.start_btn = customtkinter.CTkButton(self.sidebar, text="🚀 START BUILD", command=self.start_build_thread, height=40, font=customtkinter.CTkFont(weight="bold"))
        self.start_btn.grid(row=2, column=0, padx=20, pady=10)

        self.stop_btn = customtkinter.CTkButton(self.sidebar, text="🛑 STOP BUILD", command=self.stop_build, height=40, font=customtkinter.CTkFont(weight="bold"), fg_color="red", hover_color="darkred")
        self.stop_btn.grid(row=3, column=0, padx=20, pady=10)
        self.stop_btn.configure(state="disabled")

        self.appearance_label = customtkinter.CTkLabel(self.sidebar, text="Appearance:", anchor="w")
        self.appearance_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_menu = customtkinter.CTkOptionMenu(self.sidebar, values=["Dark", "Light", "System"], command=lambda m: customtkinter.set_appearance_mode(m))
        self.appearance_menu.grid(row=6, column=0, padx=20, pady=(10, 20))

    def create_main_content(self):
        self.tabview = customtkinter.CTkTabview(self)
        self.tabview.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        self.tabview.add("Projects")
        self.tabview.add("Build Settings")
        self.tabview.add("Distribution")
        self.tabview.add("Console")

        self.setup_projects_tab()
        self.setup_build_settings_tab()
        self.setup_distribution_tab()
        self.setup_console_tab()

    def setup_projects_tab(self):
        tab = self.tabview.tab("Projects")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        customtkinter.CTkLabel(tab, text="Select Projects to Build", font=customtkinter.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        self.project_switches = {}
        scroll_frame = customtkinter.CTkScrollableFrame(tab)
        scroll_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        scroll_frame.grid_columnconfigure(0, weight=1)
        
        for i, (key, name) in enumerate(bin.constants.projects.items()):
            switch = customtkinter.CTkSwitch(scroll_frame, text=name)
            switch.grid(row=i, column=0, padx=10, pady=10, sticky="w")
            self.project_switches[key] = switch

    def setup_build_settings_tab(self):
        tab = self.tabview.tab("Build Settings")
        tab.grid_columnconfigure(1, weight=1)

        # Workspaces
        customtkinter.CTkLabel(tab, text="Workspaces", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, padx=20, pady=(10, 5), sticky="w")
        
        self.create_path_row(tab, "Git Workspace", self.git_workspace, 1)
        self.create_path_row(tab, "Output Dir", self.result_workspace, 2)

        # Branch & Domain
        customtkinter.CTkLabel(tab, text="Git & Domain", font=customtkinter.CTkFont(weight="bold")).grid(row=3, column=0, columnspan=2, padx=20, pady=(20, 5), sticky="w")
        
        customtkinter.CTkLabel(tab, text="Branch:").grid(row=4, column=0, padx=20, pady=5, sticky="e")
        self.branch_entry = customtkinter.CTkEntry(tab, textvariable=self.git_branch)
        self.branch_entry.grid(row=4, column=1, padx=20, pady=5, sticky="ew")

        # Build Types
        customtkinter.CTkLabel(tab, text="Build Types", font=customtkinter.CTkFont(weight="bold")).grid(row=6, column=0, columnspan=2, padx=20, pady=(20, 5), sticky="w")
        self.type_checks = {}
        check_frame = customtkinter.CTkFrame(tab, fg_color="transparent")
        check_frame.grid(row=7, column=0, columnspan=2, padx=20, pady=5, sticky="w")
        
        for i, (key, name) in enumerate(bin.constants.tasks.items()):
            check = customtkinter.CTkCheckBox(check_frame, text=name)
            check.grid(row=0, column=i, padx=10, pady=5)
            self.type_checks[key] = check

    def setup_distribution_tab(self):
        tab = self.tabview.tab("Distribution")
        tab.grid_columnconfigure(1, weight=1)

        # Services
        services = [
            ("MEGA.nz", self.mega_enabled, [("MEGA_USERNAME", "User"), ("MEGA_PASSWORD", "Pass")]),
            ("FTP Server", self.ftp_enabled, [("FTP_HOST", "Host"), ("FTP_PASS", "Pass"), ("FTP_PATH", "Path"), ("FTP_BASE_URL", "Base URL")]),
            ("Discord", self.discord_enabled, [("DISCORD_WEBHOOK", "Webhook URL")]),
            ("Email", self.email_enabled, [("EMAILS", "Recipients"), ("SMTP_HOST", "SMTP Host"), ("SMTP_PORT", "Port"), ("EMAIL_USER", "User"), ("EMAIL_PASSWORD", "Pass")])
        ]

        for i, (name, var, fields) in enumerate(services):
            frame = customtkinter.CTkFrame(tab)
            frame.grid(row=i, column=0, columnspan=2, padx=20, pady=10, sticky="ew")
            frame.grid_columnconfigure(1, weight=1)
            
            customtkinter.CTkSwitch(frame, text=name, variable=var, font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
            
            field_frame = customtkinter.CTkFrame(frame, fg_color="transparent")
            field_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="ew")
            field_frame.grid_columnconfigure(list(range(len(fields)*2)), weight=1)

            for j, (env_key, lbl) in enumerate(fields):
                val = os.getenv(env_key, '')
                customtkinter.CTkLabel(field_frame, text=f"{lbl}:").grid(row=0, column=j*2, padx=5, sticky="e")
                entry = customtkinter.CTkEntry(field_frame, placeholder_text=f"Enter {lbl}")
                entry.insert(0, val)
                entry.grid(row=0, column=j*2+1, padx=5, pady=5, sticky="ew")
                setattr(self, f"dist_entry_{env_key}", entry)

    def setup_console_tab(self):
        tab = self.tabview.tab("Console")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        self.console = customtkinter.CTkTextbox(tab, font=customtkinter.CTkFont(family="Consolas", size=12))
        self.console.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.console.configure(state="disabled")

        sys.stdout = StdoutRedirector(self.console)
        sys.stderr = StdoutRedirector(self.console)

    def create_path_row(self, master, label, var, row):
        customtkinter.CTkLabel(master, text=f"{label}:").grid(row=row, column=0, padx=20, pady=5, sticky="e")
        entry = customtkinter.CTkEntry(master, textvariable=var)
        entry.grid(row=row, column=1, padx=(20, 0), pady=5, sticky="ew")
        
        btn = customtkinter.CTkButton(master, text="Browse", width=80, command=lambda: self.browse_path(var))
        btn.grid(row=row, column=2, padx=20, pady=5)

    def browse_path(self, var):
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    def load_settings(self):
        # Load project selections
        saved_projects = os.getenv('PROJECTS_REPOS', '').split(',')
        for key, switch in self.project_switches.items():
            if key in saved_projects:
                switch.select()

        # Load build types
        saved_types = os.getenv('BUILD_TYPES', '').split(',')
        for key, check in self.type_checks.items():
            if key in saved_types:
                check.select()

    def save_settings(self):
        # Update .env and os.environ
        settings = {
            'GIT_WORKSPACE': self.git_workspace.get(),
            'RESULT_WORKSPACE': self.result_workspace.get(),
            'GIT_BRANCH': self.git_branch.get(),
            'MEGA_ENABLED': str(self.mega_enabled.get()).lower(),
            'FTP_ENABLED': str(self.ftp_enabled.get()).lower(),
            'DISCORD_ENABLED': str(self.discord_enabled.get()).lower(),
            'EMAIL_ENABLED': str(self.email_enabled.get()).lower(),
        }

        # Project selection
        active_projects = [k for k, s in self.project_switches.items() if s.get()]
        settings['PROJECTS_REPOS'] = ','.join(active_projects)

        # Build types
        active_types = [k for k, c in self.type_checks.items() if c.get()]
        settings['BUILD_TYPES'] = ','.join(active_types)

        # Extra distribution settings from entries
        for env_key in ["MEGA_USERNAME", "MEGA_PASSWORD", "FTP_HOST", "FTP_PASS", "FTP_PATH", "FTP_BASE_URL", "DISCORD_WEBHOOK", "EMAILS", "SMTP_HOST", "SMTP_PORT", "EMAIL_USER", "EMAIL_PASSWORD"]:
            if hasattr(self, f"dist_entry_{env_key}"):
                val = getattr(self, f"dist_entry_{env_key}").get()
                if val: settings[env_key] = val

        for k, v in settings.items():
            os.environ[k] = v
            dotenv.set_key('.env', k, v)
        
        print(print_utils.info("Settings saved successfully."))

    def start_build_thread(self):
        self.save_settings()
        self.tabview.set("Console")
        self.start_btn.configure(state="disabled", text="🏗 BUILDING...")
        self.stop_btn.configure(state="normal")
        self.status_indicator.configure(text="● BUILDING", text_color="yellow")
        
        bin.constants.stop_requested = False
        Thread(target=self.run_build, daemon=True).start()

    def stop_build(self):
        bin.constants.stop_requested = True
        self.stop_btn.configure(state="disabled", text="🛑 STOPPING...")
        if bin.constants.current_process:
            try:
                import subprocess
                # Force kill the process tree on Windows
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(bin.constants.current_process.pid)], capture_output=True)
            except Exception as e:
                print(f"Error stopping process: {e}")

    def run_build(self):
        try:
            projects = os.getenv('PROJECTS_REPOS', '').split(',')
            global_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

            all_built_apks = [] 
            for project in projects:
                if not project: continue
                if bin.constants.stop_requested: break
                
                project_apks = build_project_module.build_project(project, global_time)
                if project_apks:
                    all_built_apks.append((project, project_apks))
            
            if all_built_apks and not bin.constants.stop_requested:
                # Store local paths for notification display
                local_folder_map = {}
                for p_name, p_apks in all_built_apks:
                    local_folder_map[p_name] = {}
                    for b_type, f_path in p_apks.items():
                        local_folder_map[p_name][b_type] = os.path.dirname(f_path)

                # Perform mass upload
                from modules import upload_module, send_module
                upload_results = upload_module.mass_upload(all_built_apks, global_time)
                
                # Send notifications
                print_utils.print_msg_box("🔔 Sending Notifications", color=print_utils.BColors.HEADER)
                for project, build_types_data in upload_results.items():
                    for build_type, urls in build_types_data.items():
                        if urls:
                            display_name = f"{project} [{build_type}]"
                            l_path = local_folder_map.get(project, {}).get(build_type)
                            send_module.send_to_discord(display_name, urls, global_time, local_path=l_path)
                            send_module.send_to_email(display_name, urls, global_time, local_path=l_path)
            
            if not bin.constants.stop_requested:
                notification_utils.send_desktop_notification(
                    "Build Successful", 
                    f"All projects ({len(all_built_apks)}) have been built and uploaded successfully!"
                )
                tkinter.messagebox.showinfo("Success", "All builds and uploads completed successfully!")
            else:
                print(print_utils.warning("Build process was stopped by user."))
        except Exception as e:
            print(print_utils.danger(f"Build Process Error: {e}"))
            notification_utils.send_desktop_notification(
                "Build Failed/Stopped", 
                f"An error occurred or build was stopped: {e}"
            )
            tkinter.messagebox.showerror("Error", f"An error occurred: {e}")
        finally:
            self.start_btn.configure(state="normal", text="🚀 START BUILD")
            self.stop_btn.configure(state="disabled", text="🛑 STOP BUILD")
            self.status_indicator.configure(text="● IDLE", text_color="gray")

if __name__ == "__main__":
    dotenv.load_dotenv()
    app = App()
    app.mainloop()
