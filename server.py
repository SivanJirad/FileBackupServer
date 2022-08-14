import socket
import os
import sys
import utils

BUFFER_SIZE = 8000


# creating and ID and sending it to the client
def create_id_and_folder_client(my_path):
    client_id2 = utils.create_id()
    new_client_path = os.path.join(my_path, client_id2)
    # crete new folder to client
    if not os.path.exists(new_client_path):
        os.makedirs(new_client_path)
    # send to client id
    client_socket.send(bytes(client_id2, "utf-8"))
    return client_id2


# pushing all files and folders from the directory with the client ID to the client directory
def search_folder_and_push_to_client(id_file_name, directorty_path, socket2):
    for root, dir, files in os.walk(directorty_path):
        for folder in dir:
            # finding the client folder by his id
            if folder == id_file_name:
                directorty_path = os.path.join(directorty_path, id_file_name)
                utils.push_all_folders(directorty_path, '', socket2)
                utils.send_message("done", socket2)
                utils.push_all_files(directorty_path, '', socket2)
                utils.send_message("it is last", socket2)
                break



# returning the path without the client ID in it
def delete_client_id_in_the_path(path2):
    parts_of_path = path2.decode("utf-8").split(os.sep)
    new_path2 = parts_of_path[1]
    for i in range(2, len(parts_of_path) - 1):
        new_path2 = os.path.join(new_path2, parts_of_path[i])
    return new_path2


# updating the dict that contains all the changes from the client
def update_data_dict(computer_id, all_computer_id, place, data_to_send, computer_id_dict):
    for client_computer_id in all_computer_id:
        # update the dictionary of all the different computers except for this one
        if client_computer_id != computer_id:
            computer_id_dict[client_computer_id][place].append(data_to_send)


if __name__ == '__main__':
    new_path = os.path.join(os.getcwd(), "Server")
    # create new folder to sever
    utils.make_folder(new_path)
    id_dict = {}
    computer_id_dict = {}
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('', int(sys.argv[1])))
    server.listen(5)

    while True:

        # accepting the next client in the line
        client_socket, client_address = server.accept()
        computer_id = utils.rec_message(client_socket).decode("utf-8")
        first_data = client_socket.recv(BUFFER_SIZE)

        # if it is the first meeting with this client
        if first_data == b'hello':
            # new client without id, server create id and open folder to save client's files"
            id_client = create_id_and_folder_client(new_path)
            print(id_client)
            # sever pull all folder from client
            utils.pull_all_folders(new_path, client_socket)
            utils.pull_all_files(new_path + os.sep, client_socket)
            id_dict.update({id_client: [computer_id]})
            save_data_dict = {"create_directory": [], "create": [], "rename_file": [],
                              "modify_directory": [], "modify": [], "delete": []}
            computer_id_dict.update({computer_id: save_data_dict})

        # if there is already a client with this ID
        elif first_data == b'already know you':
            client_socket.send(b'got it')
            client_id = client_socket.recv(BUFFER_SIZE).decode("utf-8")
            search_folder_and_push_to_client(client_id, new_path, client_socket)
            id_dict[client_id].append(computer_id)
            save_data_dict = {"create_directory": [], "create": [], "rename_file": [],
                              "modify_directory": [], "modify": [], "delete": []}
            computer_id_dict.update({computer_id: save_data_dict})

        # updating and getting updates from the client
        else:
            client_id = first_data.decode("utf-8")
            changes_dict = computer_id_dict[computer_id]
            string_flags = []
            for change in changes_dict:
                # sending the data to clients with the same ID
                all_data = changes_dict[change]
                if change == 'create_directory' and changes_dict[change] != []:
                    for data_to_send in changes_dict[change]:
                        utils.send_message(change, client_socket)
                        str_data = data_to_send.decode("utf-8").replace(client_id + os.sep, '')
                        utils.send_message(str_data, client_socket)

                if change == 'create' and changes_dict[change] != []:
                    for data_to_send in changes_dict[change]:
                        utils.send_message(change, client_socket)
                        folder_name, file_name = utils.names(client_id, data_to_send.decode("utf-8"))
                        for renames in changes_dict["rename_file"]:
                            if data_to_send in renames:
                                data_to_send = renames[1]
                                break
                        if os.path.isfile(new_path + data_to_send.decode("utf-8")):
                            utils.send_a_single_file(new_path + data_to_send.decode("utf-8"),
                                                    file_name, '', folder_name, client_socket)

                if change == 'delete' and changes_dict[change] != []:
                    for data_to_send in changes_dict[change]:
                        utils.send_message(change, client_socket)
                        str_data = data_to_send.decode("utf-8").replace(client_id + os.sep, '')
                        utils.send_message(str_data, client_socket)

                if (change == 'rename_file' or change == 'modify_directory') and changes_dict[change] != []:
                    for data_to_send in changes_dict[change]:
                        if change == "rename_file":
                            if not os.path.isfile(os.path.join(new_path , data_to_send[0].decode("utf-8").replace(client_id + os.sep, ''))):
                                string_flags.append(bytes(os.sep + data_to_send[1].decode("utf-8"), "utf-8"))
                                continue
                        utils.send_message(change, client_socket)
                        str_src_data = data_to_send[0].decode("utf-8").replace(client_id + os.sep, '')
                        utils.send_message(str_src_data, client_socket)
                        str_dest_data = data_to_send[1].decode("utf-8").replace(client_id + os.sep, '')
                        utils.send_message(str_dest_data, client_socket)

                if change == 'modify' and changes_dict[change] != []:
                    for data_to_send in changes_dict[change]:
                        utils.send_message(change, client_socket)
                        str_data = data_to_send[0].decode("utf-8").replace(os.sep + client_id + os.sep, '')
                        utils.send_message(str_data, client_socket)
                        folder_name, file_name = utils.names(client_id, data_to_send[1].decode("utf-8"))
                        utils.send_a_single_file(new_path + os.sep + data_to_send[1].decode("utf-8"),
                                                 file_name, '', folder_name, client_socket)
                        client_socket.recv(BUFFER_SIZE)

            client_socket.send(b'do nothing')
            # erase all the changes we did
            for key in computer_id_dict[computer_id]:
                #if key != "create":
                computer_id_dict[computer_id][key] = []
                # else:
                #     for item in computer_id_dict[computer_id][key]:
                #         if item not in string_flags:
                #             computer_id_dict[computer_id][key].remove(item)
            computer_id_dict[computer_id]["create"].extend(string_flags)

            data = client_socket.recv(BUFFER_SIZE)
            # updating changes in the server folder
            while data != b'no more changes':
                client_socket.send(b'got it')

                if data == b'create':
                    client_id = utils.rec_message(client_socket).decode("utf-8")
                    data2 = client_socket.recv(utils.BUFFER_SIZE)
                    utils.get_a_single_file(new_path, client_socket, data2)
                    all_computer_id = id_dict[client_id]
                    update_data_dict(computer_id, id_dict[client_id], "create", data2, computer_id_dict)
                    # time.sleep(0.1)

                elif data == b'delete':
                    client_id = utils.rec_message(client_socket).decode("utf-8")
                    data2 = utils.rec_message(client_socket)
                    utils.delete_a_single_file_or_folder(new_path, data2.decode("utf-8"))
                    all_computer_id = id_dict[client_id]
                    update_data_dict(computer_id, all_computer_id, "delete", data2, computer_id_dict)

                elif data == b'modify':
                    client_id = utils.rec_message(client_socket).decode("utf-8")
                    data_to_delete = utils.rec_message(client_socket)
                    utils.delete_a_single_file_or_folder(new_path, data_to_delete.decode("utf-8"))
                    data_to_create = client_socket.recv(utils.BUFFER_SIZE)
                    utils.get_a_single_file(new_path, client_socket, data_to_create)
                    all_computer_id = id_dict[client_id]
                    update_data_dict(computer_id, all_computer_id, "modify", [data_to_delete, data_to_create],
                                     computer_id_dict)

                elif data == b'create_directory':
                    client_id = utils.rec_message(client_socket).decode("utf-8")
                    data2 = utils.rec_message(client_socket)
                    path = os.path.join(new_path, data2.decode("utf-8"))
                    utils.make_folder(path)
                    all_computer_id = id_dict[client_id]
                    update_data_dict(computer_id, all_computer_id, "create_directory", data2, computer_id_dict)

                elif data == b'rename_file' or data == b'modify_directory':
                    client_id = utils.rec_message(client_socket).decode("utf-8")
                    data1 = utils.rec_message(client_socket)
                    src_path = os.path.join(new_path, data1.decode("utf-8"))
                    data2 = utils.rec_message(client_socket)
                    dest_path = os.path.join(new_path, data2.decode("utf-8"))
                    os.rename(src_path, dest_path)
                    all_computer_id = id_dict[client_id]
                    update_data_dict(computer_id, all_computer_id, data.decode("utf-8"), [data1, data2],
                                     computer_id_dict)

                data = client_socket.recv(BUFFER_SIZE)

        client_socket.close()