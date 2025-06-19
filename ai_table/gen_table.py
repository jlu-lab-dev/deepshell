import os
import platform
import re
import subprocess
import tempfile
import pandas as pd

from datetime import datetime


def open_excel(path: str) -> bool:
    try:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"文件不存在: {path}")

        current_os = platform.system()

        if current_os == "Windows":
            os.startfile(path)
        elif current_os == "Darwin":
            subprocess.run(["open", path], check=True)
        else:
            subprocess.run(["xdg-open", path], check=True)

        return True

    except FileNotFoundError as e:
        print(f"错误：文件未找到 - {e}")
    except subprocess.CalledProcessError as e:
        print(f"错误：命令执行失败 - {e}")
    except Exception as e:
        print(f"未知错误：{e}")

    return False


def save_excel(df, save_path=None):
    if save_path is None:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=datetime.now().strftime('%Y-%m-%d_%H-%M-%S'), suffix=".xlsx", delete=False) as tmp:
            df.to_excel(tmp, index=False, engine="openpyxl")
            return tmp.name
    else:
        df.to_excel(save_path, index=False, engine="openpyxl")
        return save_path


def generate_df(csv_data):
    lines = csv_data.split("\n")
    headers = lines[0].split(",")
    data = [line.split(",") for line in lines[1:]]
    df = pd.DataFrame(data, columns=headers)
    return df


def extract_csv_data(response_text):
    pattern = r"table>>(.*?)<<table"
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        return content
    else:
        return None


def generate_table(csv_data):
    df = generate_df(csv_data)
    save_path = save_excel(df)

    # open_excel(save_path)

    return save_path

