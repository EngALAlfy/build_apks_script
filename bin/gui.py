"""APK Builder desktop workspace. All widget access stays on the Tk thread."""
import os
import re
import sys
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from queue import Empty, Queue
from tkinter import filedialog, messagebox
import customtkinter as ctk
from bin import constants
from modules.build_service import BuildPlan, BuildService
from utils import history_utils, settings_utils

ctk.set_appearance_mode('Dark')
ctk.set_default_color_theme('blue')
C = dict(bg='#0C1018', sidebar='#101620', panel='#151D2B', inset='#101722',
         border='#283449', text='#E8EDF6', muted='#8F9EB5', accent='#668CFF',
         hover='#476DE0', green='#53D9AD', amber='#F0C274', red='#FA8697')

class QueueLog:
    """Workers enqueue text without touching Tk or blocking on rendering."""
    encoding = 'utf-8'
    def __init__(self, queue):
        self.queue = queue
    def write(self, text):
        if text:
            self.queue.put(str(text))
        return len(text)
    def flush(self):
        pass
    def isatty(self):
        return False

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('APK Builder | Release workspace')
        self.geometry('1380x880')
        self.minsize(1120, 740)
        self.configure(fg_color=C['bg'])
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.settings = settings_utils.load_settings()
        os.environ.update(self.settings)
        self.service = BuildService()
        self.logs = Queue()
        self.original_streams = sys.stdout, sys.stderr
        self.busy = False
        self.maintenance = False
        self.started_at = None
        self.closing = False
        self.active_page = 'Build workspace'
        self.project_vars = {}
        self.type_vars = {}
        self.fields = {}
        self.toggles = {}
        self.project_status = {}
        self.pages = {}
        self.nav_buttons = {}
        self.controls = []
        self._sidebar()
        self.body = ctk.CTkFrame(self, fg_color=C['bg'], corner_radius=0)
        self.body.grid(row=0, column=1, sticky='nsew', padx=30, pady=(26, 0))
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(2, weight=1)
        top = ctk.CTkFrame(self.body, fg_color='transparent')
        top.grid(row=0, column=0, sticky='ew', pady=(0, 22))
        self.page_title = self.label(top, 'Build workspace', 28, bold=True)
        self.page_title.pack(side='left')
        self.status = self.label(top, 'IDLE', 11, C['muted'], True)
        self.status.pack(side='right')
        self.subtitle = self.label(self.body, 'From source to delivery. One controlled release workflow.', 13, C['muted'])
        self.subtitle.grid(row=1, column=0, sticky='w', pady=(0, 20))
        for name in ('Build workspace', 'Build settings', 'Distribution', 'Artifacts', 'Console'):
            frame = ctk.CTkFrame(self.body, fg_color='transparent', corner_radius=0)
            frame.grid(row=2, column=0, sticky='nsew')
            frame.grid_columnconfigure(0, weight=1)
            self.pages[name] = frame
        self._workspace()
        self._settings()
        self._distribution()
        self._history()
        self._console()
        self._footer()
        self.show_page('Build workspace')
        self.update_selection()
        self.refresh_history()
        sys.stdout = QueueLog(self.logs)
        sys.stderr = sys.stdout
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Control-Return>', lambda event: self.start_build())
        self.bind('<Control-s>', lambda event: self.save_settings())
        self.after(80, self.poll)

    def label(self, parent, text, size=13, color=None, bold=False, **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=color or C['text'],
                            font=ctk.CTkFont(family='Segoe UI', size=size, weight='bold' if bold else 'normal'), **kwargs)

    def button(self, parent, text, command, primary=False, **kwargs):
        options = dict(height=36, corner_radius=7,
                       fg_color=C['accent'] if primary else C['border'],
                       hover_color=C['hover'], text_color=C['text'],
                       font=ctk.CTkFont(family='Segoe UI', size=12, weight='bold'))
        options.update(kwargs)
        return ctk.CTkButton(parent, text=text, command=command, **options)

    def panel(self, parent, **kwargs):
        return ctk.CTkFrame(parent, fg_color=C['panel'], border_width=1,
                            border_color=C['border'], corner_radius=12, **kwargs)

    def _sidebar(self):
        side = ctk.CTkFrame(self, width=214, corner_radius=0, fg_color=C['sidebar'])
        side.grid(row=0, column=0, sticky='nsew')
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(8, weight=1)
        self.label(side, 'A / B', 29, C['accent'], True).grid(row=0, column=0, sticky='w', padx=24, pady=(30, 0))
        self.label(side, 'APK BUILDER', 17, bold=True).grid(row=1, column=0, sticky='w', padx=24, pady=(8, 0))
        self.label(side, 'RELEASE OPERATIONS', 10, C['muted'], True).grid(row=2, column=0, sticky='w', padx=24, pady=(2, 34))
        for row, name in enumerate(('Build workspace', 'Build settings', 'Distribution', 'Artifacts', 'Console'), 3):
            btn = self.button(side, name, lambda n=name: self.show_page(n), anchor='w', width=174, height=42)
            btn.grid(row=row, column=0, padx=18, pady=4, sticky='ew')
            self.nav_buttons[name] = btn
        info = ctk.CTkFrame(side, fg_color=C['inset'], corner_radius=10)
        info.grid(row=9, column=0, padx=18, pady=20, sticky='ew')
        self.label(info, 'YOUR RELEASE DESK', 10, C['muted'], True).pack(anchor='w', padx=14, pady=(14, 6))
        self.label(info, 'Ctrl + Enter   Start build', 11, C['muted']).pack(anchor='w', padx=14)
        self.label(info, 'Ctrl + S         Save settings', 11, C['muted']).pack(anchor='w', padx=14, pady=(2, 14))

    def show_page(self, name):
        self.active_page = name
        self.pages[name].tkraise()
        self.page_title.configure(text=name)
        descriptions = {
            'Build workspace': 'From source to delivery. One controlled release workflow.',
            'Build settings': 'Configure your source, workspace, and build strategy.',
            'Distribution': 'Connect delivery channels and keep credentials masked.',
            'Artifacts': 'Every collected artifact, including builds saved locally.',
            'Console': 'Live output from source synchronization, builds, and delivery.',
        }
        self.subtitle.configure(text=descriptions[name])
        for key, btn in self.nav_buttons.items():
            btn.configure(fg_color=C['border'] if key == name else 'transparent',
                          text_color=C['text'] if key == name else C['muted'])
        if name == 'Artifacts':
            self.refresh_history()

    def _workspace(self):
        page = self.pages['Build workspace']
        page.grid_rowconfigure(2, weight=1)
        metrics = ctk.CTkFrame(page, fg_color='transparent')
        metrics.grid(row=0, column=0, sticky='ew', pady=(0, 22))
        metrics.grid_columnconfigure((0, 1, 2), weight=1)
        self.metrics = {}
        for col, (key, title, value) in enumerate((('projects', 'PROJECTS SELECTED', '0 / 5'),
                                                   ('jobs', 'PLANNED ARTIFACTS', '0'),
                                                   ('delivery', 'DELIVERY MODE', 'Local only'))):
            card = self.panel(metrics)
            card.grid(row=0, column=col, sticky='ew', padx=(0 if col == 0 else 6, 0 if col == 2 else 6))
            self.label(card, title, 10, C['muted'], True).pack(anchor='w', padx=20, pady=(16, 4))
            val = self.label(card, value, 25, bold=True)
            val.pack(anchor='w', padx=20, pady=(0, 17))
            self.metrics[key] = val
        heading = ctk.CTkFrame(page, fg_color='transparent')
        heading.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        self.label(heading, 'Project queue', 18, bold=True).pack(side='left')
        self.select_all = self.button(heading, 'Select all', lambda: self.select_projects(True), width=90)
        self.select_all.pack(side='right')
        self.select_none = self.button(heading, 'Clear', lambda: self.select_projects(False), width=65)
        self.select_none.pack(side='right', padx=8)
        self.controls.extend([self.select_all, self.select_none])
        scroll = ctk.CTkScrollableFrame(page, fg_color='transparent', corner_radius=0)
        scroll.grid(row=2, column=0, sticky='nsew')
        scroll.grid_columnconfigure(0, weight=1)
        saved = self.settings.get('PROJECTS_REPOS', '').split(',')
        for row, (key, name) in enumerate(constants.projects.items()):
            card = self.panel(scroll)
            card.grid(row=row, column=0, sticky='ew', pady=(0, 10))
            card.grid_columnconfigure(2, weight=1)
            var = tk.BooleanVar(value=key in saved)
            self.project_vars[key] = var
            check = ctk.CTkCheckBox(card, text='', variable=var, width=24, checkbox_width=22,
                                  checkbox_height=22, command=self.update_selection, fg_color=C['accent'])
            check.grid(row=0, column=0, rowspan=2, padx=(18, 16), pady=18)
            self.controls.append(check)
            icon = ctk.CTkFrame(card, width=42, height=42, fg_color=constants.project_colors[key], corner_radius=10)
            icon.grid(row=0, column=1, rowspan=2, padx=(0, 14), pady=16)
            icon.grid_propagate(False)
            self.label(icon, name[0], 20, bold=True).place(relx=.5, rely=.5, anchor='center')
            self.label(card, name, 15, bold=True).grid(row=0, column=2, sticky='sw', pady=(14, 0))
            self.label(card, key, 11, C['muted']).grid(row=1, column=2, sticky='nw', pady=(0, 14))
            status = self.label(card, 'Not selected', 12, C['muted'])
            status.grid(row=0, column=3, rowspan=2, padx=20, sticky='e')
            self.project_status[key] = status
        formats = self.panel(page)
        formats.grid(row=3, column=0, sticky='ew', pady=(16, 0))
        self.label(formats, 'Build formats', 14, bold=True).pack(anchor='w', padx=20, pady=(14, 10))
        options = ctk.CTkFrame(formats, fg_color='transparent')
        options.pack(fill='x', padx=20, pady=(0, 16))
        saved_types = self.settings.get('BUILD_TYPES', 'release').split(',')
        for key, name in [('debug', 'Debug APK'), ('release', 'Release APK'), ('appbundle', 'App Bundle')]:
            var = tk.BooleanVar(value=key in saved_types)
            self.type_vars[key] = var
            check = ctk.CTkCheckBox(options, text=name, variable=var, command=self.update_selection,
                                  fg_color=C['accent'], font=ctk.CTkFont(size=12))
            check.pack(side='left', padx=(0, 28))
            self.controls.append(check)

    def input_field(self, parent, key, title, hint='', secret=False):
        self.label(parent, title, 12, bold=True).pack(anchor='w', padx=20, pady=(14, 5))
        var = tk.StringVar(value=self.settings.get(key, ''))
        self.fields[key] = var
        entry = ctk.CTkEntry(parent, textvariable=var, height=38, fg_color=C['inset'],
                             border_color=C['border'], show='*' if secret else '', placeholder_text=hint)
        entry.pack(fill='x', padx=20, pady=(0, 4))
        self.controls.append(entry)
        if hint:
            self.label(parent, hint, 11, C['muted'], anchor='w').pack(fill='x', padx=20, pady=(0, 4))
        return entry

    def _settings(self):
        scroll = ctk.CTkScrollableFrame(self.pages['Build settings'], fg_color='transparent')
        scroll.pack(fill='both', expand=True)
        panel = self.panel(scroll)
        panel.pack(fill='x', pady=(0, 16))
        self.label(panel, 'Workspace & source', 18, bold=True).pack(anchor='w', padx=20, pady=(20, 0))
        for key, title in [('GIT_WORKSPACE', 'Source workspace'), ('RESULT_WORKSPACE', 'Artifact directory')]:
            self.input_field(panel, key, title)
            btn = self.button(panel, 'Choose folder', lambda k=key: self.browse(k), width=120)
            btn.pack(anchor='e', padx=20, pady=(4, 0))
            self.controls.append(btn)
        if not self.settings.get('GIT_BRANCH'):
            self.settings['GIT_BRANCH'] = 'main'
        self.input_field(panel, 'GIT_BRANCH', 'Git branch', 'Existing repositories switch to this branch and update by fast-forward only.')
        self.input_field(panel, 'GIT_USER', 'GitHub owner', 'Username or organization. Private repositories use Git Credential Manager.')
        self.label(panel, 'Local changes are protected. Commit or stash them before building.', 12, C['green']).pack(anchor='w', padx=20, pady=(12, 20))
        strategy = self.panel(scroll)
        strategy.pack(fill='x', pady=(0, 16))
        self.label(strategy, 'Build strategy', 18, bold=True).pack(anchor='w', padx=20, pady=(18, 12))
        var = tk.BooleanVar(value=self.settings.get('CLEAN_BUILD', 'true') == 'true')
        self.toggles['CLEAN_BUILD'] = var
        switch = ctk.CTkSwitch(strategy, text='Clean workspace before each project build', variable=var, progress_color=C['accent'])
        switch.pack(anchor='w', padx=20, pady=(0, 10))
        self.controls.append(switch)
        self.label(strategy, 'Disable to reuse build caches. Projects execute sequentially to keep resource use predictable.', 12, C['muted']).pack(anchor='w', padx=20, pady=(0, 20))
        actions = ctk.CTkFrame(scroll, fg_color='transparent')
        actions.pack(fill='x')
        self.button(actions, 'Save settings', self.save_settings, True, width=140).pack(side='right')
        self.button(actions, 'Validate setup', self.validate, width=140).pack(side='right', padx=10)

    def _distribution(self):
        scroll = ctk.CTkScrollableFrame(self.pages['Distribution'], fg_color='transparent')
        scroll.pack(fill='both', expand=True)
        self.label(scroll, 'Artifacts are always saved locally before delivery begins.', 13, C['green']).pack(anchor='w', pady=(0, 12))
        services = [
            ('MEGA', 'MEGA cloud', [('MEGA_USERNAME', 'Email'), ('MEGA_PASSWORD', 'Password')]),
            ('FTP', 'FTP server', [('FTP_HOST', 'Host'), ('FTP_USER', 'Username'), ('FTP_PASS', 'Password'), ('FTP_PATH', 'Remote directory'), ('FTP_BASE_URL', 'Public download base URL')]),
            ('DISCORD', 'Discord notifications', [('DISCORD_WEBHOOK', 'Webhook URL')]),
            ('SLACK', 'Slack notifications', [('SLACK_WEBHOOK', 'Incoming webhook URL')]),
            ('EMAIL', 'Email notifications', [('EMAILS', 'Recipients, separated by commas'), ('SMTP_HOST', 'SMTP host'), ('SMTP_PORT', 'SMTP port'), ('EMAIL_USER', 'Sender email'), ('EMAIL_PASSWORD', 'Password')]),
        ]
        for key, title, fields in services:
            panel = self.panel(scroll)
            panel.pack(fill='x', pady=(0, 14))
            var = tk.BooleanVar(value=self.settings.get(key + '_ENABLED', 'false') == 'true')
            self.toggles[key + '_ENABLED'] = var
            switch = ctk.CTkSwitch(panel, text=title, variable=var, command=self.update_selection,
                                  progress_color=C['accent'], font=ctk.CTkFont(size=16, weight='bold'))
            switch.pack(anchor='w', padx=20, pady=(18, 0))
            self.controls.append(switch)
            for env_key, label in fields:
                self.input_field(panel, env_key, label, secret=env_key in settings_utils.SECRET_KEYS)
            self.label(panel, ' ', 3).pack(pady=3)
        self.label(scroll, 'Notifications include download links and require MEGA or FTP delivery. Settings are saved in your user profile; no .env file is required.',
                   12, C['muted'], wraplength=780, justify='left').pack(anchor='w', pady=(0, 14))
        self.button(scroll, 'Save distribution settings', self.save_settings, True, width=220).pack(anchor='e')

    def _history(self):
        page = self.pages['Artifacts']
        bar = ctk.CTkFrame(page, fg_color='transparent')
        bar.pack(fill='x', pady=(0, 14))
        self.search = tk.StringVar()
        self.history_refresh_job = None
        self.label(bar, 'Search artifacts', 12, C['muted']).pack(side='left', padx=(0, 12))
        entry = ctk.CTkEntry(bar, textvariable=self.search, height=36, width=260,
                             fg_color=C['inset'], border_color=C['border'])
        entry.pack(side='left')
        self.search.trace_add('write', lambda *args: self.schedule_history_refresh())
        self.button(bar, 'Refresh', self.refresh_history, width=90).pack(side='right')
        self.history_frame = ctk.CTkScrollableFrame(page, fg_color='transparent')
        self.history_frame.pack(fill='both', expand=True)

    def schedule_history_refresh(self):
        if self.history_refresh_job:
            self.after_cancel(self.history_refresh_job)
        self.history_refresh_job = self.after(180, self.refresh_history)

    def refresh_history(self):
        if self.history_refresh_job:
            self.after_cancel(self.history_refresh_job)
            self.history_refresh_job = None
        for child in self.history_frame.winfo_children():
            child.destroy()
        try:
            records = history_utils.get_history()
        except (ValueError, OSError) as exc:
            self.label(self.history_frame, f'Cannot read history: {exc}', 13, C['red']).pack(pady=30)
            return
        query = self.search.get().lower()
        records = [e for e in records if query in f"{e.get('project_name', '')} {e.get('build_type', '')} {e.get('global_time', '')}".lower()]
        if not records:
            self.label(self.history_frame, 'No matching artifacts' if query else 'Your first release starts here', 20, bold=True).pack(pady=(80, 8))
            self.label(self.history_frame, 'Collected APKs and App Bundles appear here with their local paths and delivery links.', 13, C['muted'], wraplength=600).pack()
            return
        for entry in records[:100]:
            card = self.panel(self.history_frame)
            card.pack(fill='x', pady=(0, 10))
            top = ctk.CTkFrame(card, fg_color='transparent')
            top.pack(fill='x', padx=18, pady=(14, 4))
            title = f"{entry.get('project_name', 'Project')}  /  {entry.get('build_type', '').upper()}"
            self.label(top, title, 14, bold=True).pack(side='left')
            local = entry.get('local_path', '')
            available = bool(local and Path(local).is_file())
            self.label(top, 'AVAILABLE' if available else 'FILE MISSING', 10, C['green'] if available else C['amber'], True).pack(side='right')
            self.label(card, entry.get('timestamp', entry.get('global_time', ''))[:19].replace('T', '  '), 11, C['muted']).pack(anchor='w', padx=18)
            self.label(card, local or 'No local path recorded', 11, C['muted'], wraplength=760, justify='left').pack(anchor='w', padx=18, pady=4)
            actions = ctk.CTkFrame(card, fg_color='transparent')
            actions.pack(fill='x', padx=18, pady=(6, 14))
            btn = self.button(actions, 'Open folder', lambda p=local: self.open_folder(Path(p).parent), width=110)
            btn.pack(side='left')
            if not available:
                btn.configure(state='disabled')
            for service, url in entry.get('urls', {}).items():
                self.button(actions, service.upper(), lambda u=url: self.open_url(u), width=80).pack(side='left', padx=(8, 0))
            self.button(actions, 'Forget record', lambda e=entry: self.forget_record(e), width=110).pack(side='right')
            self.button(actions, 'Delete artifact', lambda e=entry: self.delete_artifact(e), width=110).pack(side='right', padx=8)
        if len(records) > 100:
            self.label(self.history_frame, 'Showing 100 records. Search to narrow the results.', 12, C['muted']).pack(pady=12)

    def _console(self):
        page = self.pages['Console']
        bar = ctk.CTkFrame(page, fg_color='transparent')
        bar.pack(fill='x', pady=(0, 12))
        self.label(bar, 'PROCESS OUTPUT', 11, C['muted'], True).pack(side='left')
        self.autoscroll = tk.BooleanVar(value=True)
        ctk.CTkSwitch(bar, text='Follow output', variable=self.autoscroll, width=130).pack(side='right')
        self.button(bar, 'Export log', self.export_log, width=100).pack(side='right', padx=8)
        self.button(bar, 'Clear', self.clear_log, width=70).pack(side='right')
        self.console = ctk.CTkTextbox(page, font=ctk.CTkFont(family='Consolas', size=12),
                                      fg_color=C['inset'], border_width=1, border_color=C['border'],
                                      text_color='#C3CFE2', wrap='word', state='disabled')
        self.console.pack(fill='both', expand=True)

    def _footer(self):
        foot = self.panel(self.body)
        foot.grid(row=3, column=0, sticky='ew', pady=(20, 22))
        foot.grid_columnconfigure(0, weight=1)
        self.activity = self.label(foot, 'Ready when you are', 13, bold=True, wraplength=500, justify='left', anchor='w')
        self.activity.grid(row=0, column=0, sticky='w', padx=20, pady=(14, 0))
        self.elapsed = self.label(foot, 'Select projects and build formats to prepare your release.', 11, C['muted'], wraplength=520, justify='left', anchor='w')
        self.elapsed.grid(row=1, column=0, sticky='w', padx=20, pady=(0, 8))
        self.progress = ctk.CTkProgressBar(foot, height=4, progress_color=C['accent'], fg_color=C['border'])
        self.progress.grid(row=2, column=0, columnspan=3, sticky='ew', padx=20, pady=(0, 16))
        self.progress.set(0)
        self.stop_btn = self.button(foot, 'Cancel', self.stop_build, width=85, state='disabled')
        self.stop_btn.grid(row=0, column=1, rowspan=2, padx=(10, 8), pady=14)
        self.start_btn = self.button(foot, 'Start build', self.start_build, True, width=140, height=42)
        self.start_btn.grid(row=0, column=2, rowspan=2, padx=(0, 20), pady=14)

    def select_projects(self, selected):
        if self.busy:
            return
        for var in self.project_vars.values():
            var.set(selected)
        self.update_selection()

    def update_selection(self):
        count = sum(v.get() for v in self.project_vars.values())
        types = sum(v.get() for v in self.type_vars.values())
        self.metrics['projects'].configure(text=f'{count} / {len(constants.projects)}')
        self.metrics['jobs'].configure(text=str(count * types))
        channels = sum((self.toggles[k].get() if k in self.toggles else False) for k in ('MEGA_ENABLED', 'FTP_ENABLED'))
        self.metrics['delivery'].configure(text=f'{channels} cloud channel' + ('s' if channels > 1 else '') if channels else 'Local only')
        if not self.busy:
            for key, var in self.project_vars.items():
                self.project_status[key].configure(text='Queued' if var.get() else 'Not selected', text_color=C['accent'] if var.get() else C['muted'])

    def collect_settings(self):
        values = {key: (var.get() if key in settings_utils.SECRET_KEYS else var.get().strip()) for key, var in self.fields.items()}
        values.update({key: str(var.get()).lower() for key, var in self.toggles.items()})
        values['PROJECTS_REPOS'] = ','.join(k for k, v in self.project_vars.items() if v.get())
        values['BUILD_TYPES'] = ','.join(k for k, v in self.type_vars.items() if v.get())
        return values

    def plan(self):
        return BuildPlan(tuple(k for k, v in self.project_vars.items() if v.get()),
                         tuple(k for k, v in self.type_vars.items() if v.get()), self.collect_settings())

    def save_settings(self):
        if self.busy:
            return
        try:
            settings_utils.save_settings(self.collect_settings())
            self.activity.configure(text='Settings saved', text_color=C['green'])
        except OSError as exc:
            messagebox.showerror('Cannot save settings', str(exc), parent=self)

    def validate(self):
        errors = self.plan().validate()
        if errors:
            messagebox.showwarning('Setup needs attention', '\n\n'.join(errors), parent=self)
        else:
            messagebox.showinfo('Setup ready', 'Project selections, tools, paths, and enabled channel settings passed validation.', parent=self)

    def start_build(self):
        if self.busy or self.service.running:
            return
        plan = self.plan()
        errors = plan.validate()
        if errors:
            messagebox.showwarning('Build needs attention', '\n\n'.join(errors), parent=self)
            return
        try:
            settings_utils.save_settings(plan.settings)
            if not self.service.start(plan):
                return
        except (OSError, ValueError) as exc:
            messagebox.showerror('Unable to start', str(exc), parent=self)
            return
        self.busy = True
        self.started_at = time.monotonic()
        self.progress.set(0)
        self.status.configure(text='BUILD IN PROGRESS', text_color=C['accent'])
        self.activity.configure(text='Preparing build queue', text_color=C['text'])
        self.start_btn.configure(state='disabled', text='Building...')
        self.stop_btn.configure(state='normal')
        for control in self.controls:
            control.configure(state='disabled')
        print('\n' + '=' * 70 + '\nBUILD SESSION STARTED\n' + '=' * 70)

    def stop_build(self):
        if self.busy:
            self.service.stop()
            self.stop_btn.configure(state='disabled')
            self.activity.configure(text='Cancelling... waiting for the active operation to finish', text_color=C['amber'])

    def poll(self):
        self.drain_logs()
        for _ in range(200):
            try:
                kind, data = self.service.events.get_nowait()
            except Empty:
                break
            if kind == 'project':
                color = C['green'] if data['state'] == 'Complete' else C['red'] if data['state'] == 'Failed' else C['accent']
                self.project_status[data['project']].configure(text=data['state'], text_color=color)
                self.progress.set(data['progress'])
            elif kind == 'stage':
                text = f"{constants.projects[data['project']]} / {data['stage']}"
                self.activity.configure(text=text)
                self.project_status[data['project']].configure(text=data['stage'])
            elif kind == 'artifact':
                self.activity.configure(text=f"Collected {data['count']} artifact(s)")
            elif kind == 'finished':
                self.finish(data)
            elif kind == 'maintenance_finished':
                self.busy = False
                self.maintenance = False
                self.start_btn.configure(state='normal')
                for control in self.controls:
                    control.configure(state='normal')
                self.refresh_history()
                failed = bool(data['errors'])
                self.status.configure(text='CLEANUP NEEDS ATTENTION' if failed else 'READY TO BUILD', text_color=C['amber'] if failed else C['green'])
                self.activity.configure(text='Cleanup incomplete; history retained for retry' if failed else 'Artifact cleanup complete')
                self.elapsed.configure(text='Review the artifact list for remaining records.')
                if failed:
                    messagebox.showwarning('Cleanup report', settings_utils.redact('\n\n'.join(data['errors'])), parent=self)
        if self.busy and not self.maintenance and self.started_at:
            seconds = int(time.monotonic() - self.started_at)
            self.elapsed.configure(text=f'Elapsed {seconds // 60:02d}:{seconds % 60:02d}  |  Live output is available in Console')
        if self.closing and not self.service.running:
            self.destroy_app()
            return
        self.after(80, self.poll)

    def finish(self, data):
        self.busy = False
        state = data['state']
        color = C['green'] if state == 'Complete' else C['red'] if state == 'Failed' else C['amber']
        self.status.configure(text=state.upper(), text_color=color)
        self.activity.configure(text=f"{state} / {data['count']} artifact(s) saved", text_color=color)
        self.elapsed.configure(text='Review Artifacts for files and delivery links. See Console for full output.')
        if state in ('Complete', 'Warning'):
            self.progress.set(1)
        self.start_btn.configure(state='normal', text='Start build')
        self.stop_btn.configure(state='disabled')
        for control in self.controls:
            control.configure(state='normal')
        for key, label in self.project_status.items():
            if label.cget('text') not in ('Complete', 'Failed', 'Not selected'):
                label.configure(text='Cancelled' if state == 'Cancelled' else 'Not completed', text_color=C['amber'])
        self.refresh_history()
        details = data['errors'] + data['warnings']
        print(f"\nSESSION {state.upper()} / {data['count']} artifact(s) saved.")
        if details:
            print('\n'.join(details))
            if not self.closing:
                messagebox.showwarning('Build report', settings_utils.redact('\n\n'.join(details)), parent=self)

    def drain_logs(self):
        chunks = []
        for _ in range(500):
            try:
                chunks.append(self.logs.get_nowait())
            except Empty:
                break
        if not chunks:
            return
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', ''.join(chunks))
        text = settings_utils.redact(text).replace('\r\n', '\n').replace('\r', '\n')
        self.console.configure(state='normal')
        self.console.insert('end', text)
        lines = int(self.console.index('end-1c').split('.')[0])
        if lines > 12000:
            self.console.delete('1.0', f'{lines - 10000}.0')
        if self.autoscroll.get():
            self.console.see('end')
        self.console.configure(state='disabled')

    def clear_log(self):
        self.console.configure(state='normal')
        self.console.delete('1.0', 'end')
        self.console.configure(state='disabled')

    def export_log(self):
        target = filedialog.asksaveasfilename(parent=self, title='Export build log', defaultextension='.log', filetypes=[('Build log', '*.log')])
        if target:
            try:
                Path(target).write_text(self.console.get('1.0', 'end-1c'), encoding='utf-8')
            except OSError as exc:
                messagebox.showerror('Export failed', str(exc), parent=self)

    def browse(self, key):
        folder = filedialog.askdirectory(parent=self, title='Choose workspace')
        if folder:
            self.fields[key].set(folder)

    def open_folder(self, folder):
        try:
            if not Path(folder).is_dir():
                raise FileNotFoundError(f'Folder no longer exists: {folder}')
            os.startfile(str(folder))
        except OSError as exc:
            messagebox.showerror('Cannot open folder', str(exc), parent=self)

    def open_url(self, url):
        if url.startswith(('https://', 'http://', 'ftp://')):
            webbrowser.open(url)

    def forget_record(self, entry):
        if self.busy:
            return
        if messagebox.askyesno('Forget history record', 'Remove this record from history? Local files and uploaded artifacts will be kept.', parent=self):
            try:
                history_utils.remove_entry(entry['id'])
                self.refresh_history()
            except (OSError, ValueError) as exc:
                messagebox.showerror('Cannot update history', str(exc), parent=self)

    def delete_artifact(self, entry):
        if self.busy or self.service.running:
            return
        details = ['The local APK or App Bundle']
        if entry.get('mega_handles', {}).get('mega'):
            details.append('The tracked MEGA upload')
        if entry.get('discord_message_ids'):
            details.append('Tracked Discord notifications')
        text = f"Permanently delete {entry.get('project_name', 'this artifact')}?\n\n" + '\n'.join(details)
        if entry.get('urls', {}).get('ftp'):
            text += '\n\nFTP files must be removed on the FTP server separately.'
        if entry.get('slack_notified'):
            text += '\n\nSlack notifications remain in the channel; incoming webhooks cannot delete messages.'
        if not messagebox.askyesno('Delete artifact', text, parent=self):
            return
        if self.service.delete_artifact(entry['id'], self.fields['RESULT_WORKSPACE'].get()):
            self.busy = True
            self.maintenance = True
            self.start_btn.configure(state='disabled')
            self.stop_btn.configure(state='disabled')
            self.status.configure(text='CLEANING UP', text_color=C['amber'])
            self.activity.configure(text='Removing artifact and tracked remote resources...')
            self.elapsed.configure(text='The history record will be kept if any deletion fails.')
            for control in self.controls:
                control.configure(state='disabled')

    def close(self):
        if self.maintenance:
            messagebox.showinfo('Cleanup in progress', 'Wait for artifact cleanup to finish before closing.', parent=self)
            return
        if self.busy or self.service.running:
            if not messagebox.askyesno('Build in progress', 'Cancel the build and close when the active operation finishes?', parent=self):
                return
            self.closing = True
            self.stop_build()
        else:
            self.destroy_app()

    def destroy_app(self):
        sys.stdout, sys.stderr = self.original_streams
        self.destroy()
