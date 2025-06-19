import requests

from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from http import HTTPStatus
from urllib.parse import urlparse, unquote
from pathlib import PurePosixPath
from dashscope import ImageSynthesis




class AiDrawing:
    # def simple_call(self, prompt):
    #     rsp = dashscope.ImageSynthesis.call(model=dashscope.ImageSynthesis.Models.wanx_v1,
    #                               prompt=prompt,
    #                               n=2,
    #                               size='1024*1024')
    #     if rsp.status_code == HTTPStatus.OK:
    #         print(rsp.output)
    #         print(rsp.usage)
    #         # save file to current directory
    #         for result in rsp.output.results:
    #             file_name = PurePosixPath(unquote(urlparse(result.url).path)).parts[-1]
    #             file_path = '~/图片/%s' % file_name
    #             print(file_path)
    #             with open(file_path, 'wb+') as f:
    #                 f.write(requests.get(result.url).content)
    #             self.complete_drawing_signal.emit(file_path)
    #     else:
    #         print('Failed, status_code: %s, code: %s, message: %s' %
    #               (rsp.status_code, rsp.code, rsp.message))

    # 创建异步任务
    @staticmethod
    def create_async_task(prompt):
        rsp = None
        try:
            rsp = ImageSynthesis.async_call(model=ImageSynthesis.Models.wanx_v1,
                                            prompt=prompt,
                                            n=1,
                                            size='1024*1024',
                                            style='<chinese painting>')
        except Exception as e:
            print(f"image async_call 异常: {e}")
            return None
        return rsp

    # 获取异步任务信息
    @staticmethod
    def fetch_task_status(task):
        status = None
        try:
            status = ImageSynthesis.fetch(task)

        except Exception as e:
            print(f"image fetch 异常: {e}")
            return None

        if status:
            if status.status_code == HTTPStatus.OK:
                print("task status:" + status.output.task_status)
                return status.output.task_status
            else:
                print('Failed, status_code: %s, code: %s, message: %s' %
                      (status.status_code, status.code, status.message))
        else:
            print("status is None.")

        return None


    # 等待异步任务结束
    @staticmethod
    def wait_task(task):
        rsp = None
        try:
            rsp = ImageSynthesis.wait(task)
        except Exception as e:
            print(f"image wait 异常: {e}")
            return None

        if rsp:
            if rsp.status_code == HTTPStatus.OK:
                print(rsp.output.task_status)
                for result in rsp.output.results:
                    file_name = PurePosixPath(unquote(urlparse(result.url).path)).parts[-1]
                    file_path = '/home/'+current_user+'/图片/%s' % file_name
                    print(file_path)
                    with open(file_path, 'wb+') as f:
                        f.write(requests.get(result.url).content)
                    return file_path
            else:
                print('Failed, status_code: %s, code: %s, message: %s' %
                      (rsp.status_code, rsp.code, rsp.message))
                return None

    # 取消异步任务，只有处于PENDING状态的任务才可以取消
    @staticmethod
    def cancel_task(task):
        print("cancel_task")
        rsp = None
        try:
            rsp = ImageSynthesis.cancel(task)
            print("cancel_task")
        except Exception as e:
            print(f"image cancel 异常: {e}")
            return

        if rsp:
            if rsp.status_code == HTTPStatus.OK:
                print("cancel status:" + rsp.output.task_status)
            else:
                print('Failed, status_code: %s, code: %s, message: %s' %
                      (rsp.status_code, rsp.code, rsp.message))
        else:
            print("rsp is None")


class AiDrawingTask(QThread):
    complete_signal = pyqtSignal(str)
    prompt = ""

    def __init__(self):
        super(AiDrawingTask, self).__init__()
        self.prompt = ""
        self.task_result = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.timeout_handle)
        # TODO:
        # path = '/home/'+current_user+'/图片/'
        # if not os.path.exists(path):
        #     print("目录：" + path + " 不存在")
        #     os.mkdir(path)

    def start_timer(self, time):
        self.timer.start(time)

    def timeout_handle(self):
        print("timeout_handle")
        self.timer.stop()
        if self.task_result:
            status = AiDrawing.fetch_task_status(self.task_result)
            if status == "PENDING":
                AiDrawing.cancel_task(self.task_result)
            elif status == "RUNNING":
                print("Task can't Cancel.")
            # self.task_info = None

    def set_prompt(self, prompt):
        self.prompt = prompt

    def run(self):
        self.task_result = AiDrawing.create_async_task(self.prompt)
        if self.task_result:
            if self.task_result.status_code == HTTPStatus.OK:
                AiDrawing.fetch_task_status(self.task_result)
                file_path = AiDrawing.wait_task(self.task_result)
                if file_path:
                    self.complete_signal.emit(file_path)
            else:
                print('Failed, status_code: %s, code: %s, message: %s' %
                      (self.task_result.status_code, self.task_result.code, self.task_result.message))
                self.complete_signal.emit("fail: " + self.task_result.message)

