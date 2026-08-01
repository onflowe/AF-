"""找到backend目录，将对应的相对路径换成绝对路径"""

import os

def root_path()->str:
    # current_dir 当前文件所在文件夹路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # root 该文件夹所在的文件夹路径 即backend路径
    root = os.path.dirname(current_dir)
    return root

def get_abs_path(path:str):
    root = root_path()
    return os.path.join(root, path)

if __name__ == "__main__":
    print(get_abs_path("data"))