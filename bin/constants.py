# Define the projects names
projects = {
    "hurryApp": "Customer App",
    "BranchManager": "Vendor App",
    "delivery_captin": "Captain App",
    "hurryapp_onground": "OnGround App",
    "hurryApp_Manager": "Admin App",
}

# Define brand colors for projects (Hex codes)
project_colors = {
    "hurryApp": "#007bff",          # Blue
    "BranchManager": "#28a745",      # Green
    "delivery_captin": "#dc3545",    # Red
    "hurryapp_onground": "#17a2b8",  # Teal
    "hurryApp_Manager": "#6610f2",   # Purple
}

# Define tasks
tasks = {
    "debug": "Debug Build",
    "release": "Release Build",
    "appbundle": "App Bundle Build",
}

# State variables for build process control
current_process = None
stop_requested = False
