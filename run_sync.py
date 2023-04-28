#!/usr/bin/env python3

import os
import platform
import subprocess
import threading
import tkinter
from tkinter import ttk


class LiftingTk(tkinter.Tk):
    def mainloop(self, n=0):
        self.attributes("-topmost", True)
        if platform.system() == 'Darwin':
            tmpl = 'tell application "System Events" to set frontmost of every process whose unix id is {} to true'
            script = tmpl.format(os.getpid())
            subprocess.check_call(['/usr/bin/osascript', '-e', script])
        self.after(0, lambda: self.attributes("-topmost", False))
        super().mainloop(n)


def run_as_thread(func):
    il = []
    thread = threading.Thread(target=func, kwargs={"item_list": il})
    thread.start()
    thread.join()
    return il


def output_app(text):
    app_root = LiftingTk()
    frame = ttk.Frame(app_root)
    output = tkinter.Text(frame, wrap=tkinter.WORD, state=tkinter.NORMAL, height=25, width=120, font=("Menlo", "12"))
    output.insert(tkinter.END, text)
    output.config(state=tkinter.DISABLED)
    output.grid(row=0, column=0)
    frame.grid(row=0, column=0)
    app_root.title("Program Output")
    app_root.mainloop()


def run_proc(*args, item_list=[]):
    proc = subprocess.run(*args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    item_list.append(proc.stdout)


def run(*args, pbar: ttk.Progressbar = None):
    pbar.start()
    output = run_as_thread(lambda item_list: run_proc(*args, item_list=item_list))
    pbar.stop()
    output_app(output[0])


def local_proc(filename):
    return os.path.join(os.path.dirname(__file__), filename)


def main():
    root = LiftingTk()
    root.title("File Sync")
    frame = ttk.Frame(root)
    pbar = ttk.Progressbar(frame, orient=tkinter.HORIZONTAL, mode="indeterminate")
    button1 = ttk.Button(frame, text="Sync From", command=lambda: run(local_proc("syncfrom.sh"), pbar=pbar))
    button2 = ttk.Button(frame, text="Sync To", command=lambda: run(local_proc("syncto.sh"), pbar=pbar))
    button1.grid(row=0, column=0)
    button2.grid(row=0, column=1)
    pbar.grid(row=1, column=0, columnspan=2)
    frame.grid(row=0, column=0)
    root.mainloop()


if __name__ == '__main__':
    main()
