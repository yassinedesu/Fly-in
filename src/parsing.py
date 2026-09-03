import sys
from typing import TextIO
#from graph import Hub, Connection, MapParse


class   ParsingError(Exception):
    """having 2 args, line number & message"""
    def __init__(self, line_n: int, message: str):
        self.line_n = line_n
        self.message = message

    def print_error(self):
        print(f"Error acquired: line-{self.line_n}: message --> {self.message}")

class   FileCheck():

    def __init__(self):
        self.args_list: list

    @staticmethod
    def file_to_lists():
        if len(sys.argv) < 2:
            print("No map was passed\nUsage: python fly-in.py <filename>")
            sys.exit(1)
        lll: list
        try:
            with open(sys.argv[1], "r") as lst:
                lll = enumerate(lst.read().splitlines(), 1)
            return lll
        except FileNotFoundError as e:
            print(f"Error: {e}")
            return None
    
    @staticmethod
    def is_drones(drones_nb: str) -> bool:
        if "nb_drones" in drones_nb:
            return True
        return False

    @staticmethod
    def is_start_hub(start_hub: str) -> bool:
        if "start_hub" in start_hub:
            return True
        return False

    @staticmethod
    def is_end_hub(end_hub: str) -> bool:
        if "end_hub" in end_hub:
            return True
        return False

    @staticmethod
    def is_connection(connection: str) -> bool:
        if "connection" in connection:
            return True
        return False    

    @staticmethod
    def args_check(lst: list):
        count = 0
        for i in lst:
            if "#" in i:
                continue
            if FileCheck.is_drones(i) or FileCheck.is_start_hub or FileCheck.is_end_hub:
                count += 1
            
                


    def args_ready(self):
        self.args_list = self.file_to_lists()

class   Nb_Drones():
    pass

class   Hubs():
    pass

class   Connections():
    pass

if __name__ == "__main__":
    file = FileCheck()
    lll = file.file_to_lists()
    if lll is None:
        print("file is empty")
        exit()
    print("============")
    for i in lll:
        print("========================")
        print(i)
        print("========================")