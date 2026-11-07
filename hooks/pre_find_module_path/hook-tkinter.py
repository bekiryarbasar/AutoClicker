def pre_find_module_path(hook_api):
    # The packaged Tcl/Tk runtime data is supplied explicitly for this build.
    # Keep Python's tkinter package on the normal module search path.
    return
