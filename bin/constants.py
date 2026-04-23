# Define the projects names
projects = {
    "hurryApp": "HurryApp",
    "restaurant_manager": "Restaurant Manager",
    "BranchManager": "Branch Manager",
    "delivery_captin": "Captain App",
    "hurryapp_onground": "OnGround App",
    "hurryApp_Manager": "Admin App",
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
