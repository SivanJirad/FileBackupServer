import sys
import utils
import socket
import os
import time
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

BUFFER_SIZE = 8000


# send "hello" to server, server knows that he needs to send new id to client
def connect_with_server(socket):
    socket.send(b'hello')
    client_id = socket.recv(BUFFER_SIZE).decode("utf-8")
    return client_id


# the client sends the server all the folder he wants to backup
def no_id(client_id, directory_path, socket):
    utils.push_all_folders(directory_path, client_id, socket)
    # The client notifies the server that has finished sending the folder names to it
    utils.send_message("done", socket)
    utils.push_all_files(directory_path, client_id, socket)
    utils.send_message("it is last", socket)


# the client gets the server all the folder of the client with the same id
def with_id(client_id, directory_path, socket):
    socket.send(bytes(client_id, "utf-8"))
    utils.pull_all_folders(directory_path, socket)
    utils.pull_all_files(directory_path, socket)


def send_directory(dest_path, path_folder_client, client_id, socket):
    str = dest_path.replace(path_folder_client, "")
    utils.send_message(client_id + str, socket)


# sending the old and new name of the folder we renamed
def send_new_folder_path(src_path, dest_path, directory, socket, client_id):
    str_src_path = src_path.replace(directory, "")
    str_dest_path = dest_path.replace(directory, "")
    path_dest_arr = str_dest_path.split(os.sep)
    path_src_arr = str_src_path.split(os.sep)
    folder_new_name = path_dest_arr[0]
    folder_old_name = path_src_arr[0]
    if folder_new_name == folder_old_name:
        for i in range(1, len(path_dest_arr)):
            if path_dest_arr[i] == path_src_arr[i]:
                folder_old_name = os.path.join(folder_old_name, path_src_arr[i])
                folder_new_name = os.path.join(folder_new_name, path_dest_arr[i])
            if path_dest_arr[i] != path_src_arr[i]:
                folder_old_name = os.path.join(folder_old_name, path_src_arr[i])
                folder_new_name = os.path.join(folder_new_name, path_dest_arr[i])
                break
    utils.send_message(os.path.join(client_id, folder_old_name), socket)
    utils.send_message(os.path.join(client_id, folder_new_name), socket)


# checking if other clients with same ID did changes in the folder
def check_if_need_to_update(sock, directory, changes_from_server_dict, client_id):
    sock.send(bytes(client_id, "utf-8"))
    data = sock.recv(BUFFER_SIZE)
    flag_entered_to_dict = 0
    while data != b'do nothing':
        sock.send(b'got it')
        flag_entered_to_dict = 1
        if data == b'create_directory':
            data2 = utils.rec_message(sock).decode("utf-8")
            path = os.path.join(directory, data2)
            utils.make_folder(path)
            changes_from_server_dict["create_directory"].append(path)

        elif data == b'create':
            data2 = sock.recv(utils.BUFFER_SIZE)
            data3 = data2.decode("utf-8")
            if data3 != '':
                if data3[0] == os.sep:
                    data3 = data3.replace(os.sep, '', 1)
            changes_from_server_dict["create"].append(directory + os.sep + data3)
            utils.get_a_single_file(directory + os.sep, sock, data2)

        elif data == b'rename_file' or data == b'modify_directory':
            data1 = utils.rec_message(sock)
            src_path = os.path.join(directory, data1.decode("utf-8"))
            data2 = utils.rec_message(sock)
            dest_path = os.path.join(directory, data2.decode("utf-8"))
            changes_from_server_dict[data.decode("utf-8")].append([src_path, dest_path])
            os.rename(os.path.normpath(src_path), os.path.normpath(dest_path))

        elif data == b'modify':
            data_to_delete = utils.rec_message(sock).decode("utf-8")
            data_to_create = utils.rec_message(sock).decode("utf-8")
            if data_to_create[0] == os.sep:
                data_to_create = data_to_create.replace(os.sep, '', 1)
            changes_from_server_dict["delete"].append(client_id + data_to_delete)
            changes_from_server_dict["create"].append(directory + os.sep + data_to_create)
            changes_from_server_dict["modify"].append(directory + os.sep + data_to_create)
            if data_to_delete[0] == os.sep:
                data_to_delete = data_to_delete.replace(os.sep, '', 1)
            utils.delete_a_single_file_or_folder(directory, data_to_delete)
            utils.get_a_single_file(directory + os.sep, sock, bytes(data_to_create, "utf-8"))

        elif data == b'delete':
            data2 = utils.rec_message(sock)
            for root, dirs, files in os.walk(directory + os.sep + data2.decode("utf-8"), topdown=False):
                for file in files:
                    changes_from_server_dict["delete"].append(client_id + root.replace(directory, '') + os.sep + file)
                for folder in dirs:
                    changes_from_server_dict["delete"].append(client_id + root.replace(directory, '') + os.sep + folder)
            changes_from_server_dict["delete"].append(client_id + os.sep + data2.decode("utf-8"))
            utils.delete_a_single_file_or_folder(directory, data2.decode("utf-8"))

        data = sock.recv(BUFFER_SIZE)

    return flag_entered_to_dict


# checking if the file that was created is a temporary file
def check_if_tmp(path):
    arr_path = path.split('.')
    if arr_path[len(arr_path) - 1] == "tmp" or arr_path[len(arr_path) - 1] == "TMP":
        return True


class Watcher:

    def __init__(self, directory, times, ip, port, client_id, computer_id, handler):
        self.observer = Observer()
        self.directory = directory
        self.time_for_connect = times
        self.ip = ip
        self.port = port
        self.client_id = client_id
        self.computer_id = computer_id
        self.handler = handler
        self.changes_from_server_dict = {"delete": [], "create": [], "create_directory": [], "rename_file": [],
                                         "modify_directory": [], "modify": []}

    def run(self):
        self.observer.schedule(self.handler, self.directory, recursive=True)
        self.observer.start()

        #try:
        while True:
            self.handler.close_socket()
            time.sleep(self.time_for_connect)
            sock_new = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.handler.set_socket(sock_new)
            sock_new.connect((self.ip, self.port))
            utils.send_message(self.computer_id, sock_new)
            flag_erase_dict = check_if_need_to_update(sock_new, self.directory, self.changes_from_server_dict,
                                                          self.client_id)
            # the dict that contains all the changes we made
            dict = self.handler.get_dict()
            # remove duplicates from list
            for key in dict:
                if key != "rename_file" and key != "modify_directory":
                    dict[key] = list(dict.fromkeys(dict[key]))

            # sending the server all the changes we did' except from those we got from him
            for item in dict["create_directory"]:
                if item not in self.changes_from_server_dict["create_directory"]:
                    utils.send_message("create_directory", sock_new)
                    utils.send_message(self.client_id, sock_new)
                    send_directory(item, self.directory, self.client_id, sock_new)

            for item in dict["create"]:
                if item not in self.changes_from_server_dict["create"]:
                    utils.send_message("create", sock_new)
                    utils.send_message(self.client_id, sock_new)
                    folder_name, file_name = utils.names(self.directory, item)
                    for files in dict["rename_file"]:
                        if item in files:
                            item = files[1]
                            break
                    utils.send_a_single_file(item, file_name, os.sep + self.client_id, folder_name, sock_new)

            for item in dict["rename_file"]:
                if item not in self.changes_from_server_dict["rename_file"]:
                    utils.send_message("rename_file", sock_new)
                    utils.send_message(self.client_id, sock_new)
                    folder_name1, file_name1 = utils.names(self.directory, item[0])
                    utils.send_message(self.client_id + folder_name1 + os.sep + file_name1, sock_new)
                    folder_name2, file_name2 = utils.names(self.directory, item[1])
                    utils.send_message(self.client_id + folder_name2 + os.sep + file_name2, sock_new)

            for item in dict["modify_directory"]:
                do_change = 1
                for change in self.changes_from_server_dict["modify_directory"]:
                    if change[0] in item[0]:
                        do_change = 0
                if do_change == 1:
                    utils.send_message("modify_directory", sock_new)
                    utils.send_message(self.client_id, sock_new)
                    send_new_folder_path(item[0], item[1], self.directory, sock_new, self.client_id)

            for item in dict["modify"]:
                if item not in self.changes_from_server_dict["modify"]:
                    if os.path.isfile(item):
                        utils.send_message("modify", sock_new)
                        utils.send_message(self.client_id, sock_new)
                        delete_path = item.replace(self.directory, "")
                        utils.send_message(os.path.join(self.client_id, delete_path), sock_new)
                        folder_name, file_name = utils.names(self.directory, item)
                        utils.send_a_single_file(item, file_name, os.sep + self.client_id, folder_name, sock_new)

            for item in dict["delete"]:
                if item not in self.changes_from_server_dict["delete"]:
                    utils.send_message("delete", sock_new)
                    utils.send_message(self.client_id, sock_new)
                    utils.send_message(item, sock_new)

            self.handler.set_list_empty()
            if self.handler.flag_rename_file == 1:
                if self.handler.counter_rename == 2:
                    self.handler.initialize_counter_rename()
                    self.handler.flag_rename_file = 0
                else:
                    self.handler.raise_counter_rename()
            if self.handler.flag_create_file == 1:
                if self.handler.counter_create == 2:
                    self.handler.initialize_counter_create()
                    self.handler.flag_create_file = 0
                else:
                    self.handler.raise_counter_create()

            if flag_erase_dict != 1:
                for key in self.changes_from_server_dict:
                    self.changes_from_server_dict[key] = []

            sock_new.send(b"no more changes")
        #except:
            #self.observer.stop()
            #self.observer.join()


class MyHandler(FileSystemEventHandler):

    def __init__(self, ip, port, sock, client_id, path_folder_client):
        FileSystemEventHandler.__init__(self)
        self.dict_change = {"delete": [], "create": [], "create_directory": [], "rename_file": [],
                            "modify_directory": [], "modify": []}
        self.socket = sock
        self.ip = ip
        self.port = port
        self.client_id = client_id
        self.path_folder_client = path_folder_client
        self.flag_create_file = 0
        self.flag_create_folder = 0
        self.flag_rename_folder = 0
        self.flag_rename_file = 0
        self.counter_create = 0
        self.counter_rename = 0

    def set_list_empty(self):
        for key in self.dict_change:
            self.dict_change[key] = []

    def get_dict(self):
        return self.dict_change

    def close_socket(self):
        self.socket.close()

    def set_socket(self, sock):
        self.socket = sock

    def raise_counter_create(self):
        self.counter_create = self.counter_create + 1

    def raise_counter_rename(self):
        self.counter_rename = self.counter_rename + 1

    def initialize_counter_create(self):
        self.counter_create = 0

    def initialize_counter_rename(self):
        self.counter_rename = 0

    # create file
    def on_created(self, event):
        if event.is_directory:
            self.dict_change["create_directory"].append(event.src_path)
        else:
            if not check_if_tmp(event.src_path):
                self.flag_create_file = 1
                self.dict_change["create"].append(event.src_path)
                self.initialize_counter_create()

    def on_deleted(self, event):
        if os.path.isdir(event.src_path):
            new_string = event.src_path.replace(self.path_folder_client, "")
            self.dict_change["delete"].append(self.client_id + new_string)
        else:
            if not check_if_tmp(event.src_path):
                new_string = event.src_path.replace(self.path_folder_client, "")
                self.dict_change["delete"].append(self.client_id + new_string)

    def on_modified(self, event):
        self.flag_rename_folder = 0
        if not event.is_directory:
            if self.flag_create_file == 0 and self.flag_rename_file == 0 and not check_if_tmp(event.src_path):
                self.dict_change["modify"].append(event.src_path)
            self.flag_rename_file = 0
            self.flag_create_file = 0

    def on_moved(self, event):
        if event.is_directory:
            if self.flag_rename_folder == 0:
                self.flag_rename_folder = 1
                self.dict_change["modify_directory"].append([event.src_path, event.dest_path])
        else:
            # if the name of the file was changed, and the file didn't only move
            dest_path_arr = event.dest_path.split(os.sep)
            src_path_arr = event.src_path.split(os.sep)
            len_src_path_arr = len(src_path_arr)
            if src_path_arr[len_src_path_arr - 1] != dest_path_arr[len_src_path_arr - 1]:
                if not check_if_tmp(event.src_path) and not check_if_tmp(event.dest_path):
                    self.dict_change["rename_file"].append([event.src_path, event.dest_path])
                    self.flag_rename_file = 1
                    self.initialize_counter_rename()


if __name__ == "__main__":
    ip = sys.argv[1]
    port = int(sys.argv[2])
    directory_path = sys.argv[3]
    time_for_connect = float(sys.argv[4])
    client_id = ''
    computer_id = utils.create_id()

    socket_first = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_first.connect((ip, port))
    utils.send_message(computer_id, socket_first)

    # if there are only four arguments (no ID)
    if len(sys.argv) == 5:
        client_id = connect_with_server(socket_first)
        no_id(client_id, directory_path, socket_first)
    else:
        client_id = sys.argv[5]
        utils.make_folder(directory_path)
        utils.send_message("already know you", socket_first)
        with_id(client_id, directory_path, socket_first)

    w = Watcher(directory_path, time_for_connect, ip, port, client_id, computer_id,
                MyHandler(ip, port, socket_first, client_id, directory_path))
    w.run()