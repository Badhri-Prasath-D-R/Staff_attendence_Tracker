import streamlit.web.cli as stcli
import os, sys

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    # This now correctly points to the BUNDLED app.py inside the temp folder
    target_file = get_resource_path("app.py")
    
    sys.argv = [
        "streamlit",
        "run",
        target_file,
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())