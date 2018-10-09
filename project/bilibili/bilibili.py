# -*- coding:UTF-8  -*-
"""
bilibili用户相簿爬虫
https://www.bilibili.com/
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
import os
import time
import traceback
from common import *

ALBUM_COUNT_PER_PAGE = 30


# 获取指定页数的全部相簿
def get_one_page_album(account_id, page_count):
    # https://api.vc.bilibili.com/link_draw/v1/doc/doc_list?uid=116683&page_num=1&page_size=30&biz=all
    api_url = "https://api.vc.bilibili.com/link_draw/v1/doc/doc_list"
    query_data = {
        "uid": account_id,
        "page_num": page_count,
        "page_size": ALBUM_COUNT_PER_PAGE,
        "biz": "all",
    }
    api_response = net.http_request(api_url, method="GET", fields=query_data, json_decode=True)
    result = {
        "album_id_list": [],  # 全部相簿id
        "is_over": False,  # 是否最后一页相簿
    }
    if api_response.status != net.HTTP_RETURN_CODE_SUCCEED:
        raise crawler.CrawlerException(crawler.request_failre(api_response.status))
    if not crawler.check_sub_key(("data",), api_response.json_data):
        raise crawler.CrawlerException("返回信息'data'字段不存在\n%s" % api_response.json_data)
    if not crawler.check_sub_key(("items",), api_response.json_data["data"]):
        raise crawler.CrawlerException("返回信息'items'字段不存在\n%s" % api_response.json_data)
    for album_info in api_response.json_data["data"]["items"]:
        # 获取日志id
        if not crawler.check_sub_key(("doc_id",), album_info):
            raise crawler.CrawlerException("相簿信息'doc_id'字段不存在\n%s" % album_info)
        if not crawler.is_integer(album_info["doc_id"]):
            raise crawler.CrawlerException("相簿信息'doc_id'字段类型不正确\n%s" % album_info)
        result["album_id_list"].append(int(album_info["doc_id"]))
    return result


# 获取指定id的相簿
def get_album_page(album_id):
    # https://api.vc.bilibili.com/link_draw/v1/doc/detail?doc_id=739722
    api_url = "https://api.vc.bilibili.com/link_draw/v1/doc/detail"
    query_data = {
        "doc_id": album_id,
    }
    api_response = net.http_request(api_url, method="GET", fields=query_data, json_decode=True)
    result = {
        "photo_url_list": [],  # 全部图片地址
    }
    if api_response.status != net.HTTP_RETURN_CODE_SUCCEED:
        raise crawler.CrawlerException(crawler.request_failre(api_response.status))
    if not crawler.check_sub_key(("data",), api_response.json_data):
        raise crawler.CrawlerException("返回信息'data'字段不存在\n%s" % api_response.json_data)
    if not crawler.check_sub_key(("item",), api_response.json_data["data"]):
        raise crawler.CrawlerException("返回信息'items'字段不存在\n%s" % api_response.json_data)
    if not crawler.check_sub_key(("pictures",), api_response.json_data["data"]["item"]):
        raise crawler.CrawlerException("返回信息'items'字段不存在\n%s" % api_response.json_data)
    for photo_info in api_response.json_data["data"]["item"]["pictures"]:
        if not crawler.check_sub_key(("img_src",), photo_info):
            raise crawler.CrawlerException("图片信息'img_src'字段不存在\n%s" % photo_info)
        result["photo_url_list"].append(photo_info["img_src"])
    return result


class BiliBili(crawler.Crawler):
    def __init__(self):
        # 设置APP目录
        crawler.PROJECT_APP_PATH = os.path.abspath(os.path.dirname(__file__))

        # 初始化参数
        sys_config = {
            crawler.SYS_DOWNLOAD_PHOTO: True,
        }
        crawler.Crawler.__init__(self, sys_config)

        # 解析存档文件
        # account_name  last_album_id
        self.account_list = crawler.read_save_data(self.save_data_path, 0, ["", "0"])

    def main(self):
        # 循环下载每个id
        thread_list = []
        for account_id in sorted(self.account_list.keys()):
            # 提前结束
            if not self.is_running():
                break

            # 开始下载
            thread = Download(self.account_list[account_id], self)
            thread.start()
            thread_list.append(thread)

            time.sleep(1)

        # 等待子线程全部完成
        while len(thread_list) > 0:
            thread_list.pop().join()

        # 未完成的数据保存
        if len(self.account_list) > 0:
            file.write_file(tool.list_to_string(list(self.account_list.values())), self.temp_save_data_path)

        # 重新排序保存存档文件
        crawler.rewrite_save_file(self.temp_save_data_path, self.save_data_path)

        log.step("全部下载完毕，耗时%s秒，共计图片%s张" % (self.get_run_time(), self.total_photo_count))


class Download(crawler.DownloadThread):
    def __init__(self, account_info, main_thread):
        crawler.DownloadThread.__init__(self, account_info, main_thread)
        self.account_id = self.account_info[0]
        if len(self.account_info) >= 3 and self.account_info[2]:
            self.display_name = self.account_info[2]
        else:
            self.display_name = self.account_info[0]
        self.step("开始")

    # 获取所有可下载相簿
    def get_crawl_list(self):
        page_count = 1
        unique_list = []
        album_id_list = []
        is_over = False
        while not is_over:
            self.main_thread_check()  # 检测主线程运行状态
            self.step("开始解析第%s页相簿" % page_count)

            # 获取一页相簿
            try:
                album_pagination_response = get_one_page_album(self.account_id, page_count)
            except crawler.CrawlerException as e:
                self.error("第%s页相簿解析失败，原因：%s" % (page_count, e.message))
                raise

            self.trace("第%s页解析的全部相簿：%s" % (page_count, album_pagination_response["album_id_list"]))
            self.step("第%s页解析获取%s个相簿" % (page_count, len(album_pagination_response["album_id_list"])))

            # 寻找这一页符合条件的相簿
            for album_id in album_pagination_response["album_id_list"]:
                # 检查是否达到存档记录
                if album_id > int(self.account_info[1]):
                    # 新增相簿导致的重复判断
                    if album_id in unique_list:
                        continue
                    else:
                        album_id_list.append(album_id)
                        unique_list.append(album_id)
                else:
                    is_over = True
                    break

            if not is_over:
                if 0 < len(album_pagination_response["album_id_list"]) < ALBUM_COUNT_PER_PAGE:
                    page_count += 1
                else:
                    is_over = True

        return album_id_list

    # 解析单个相簿
    def crawl_album(self, album_id):
        self.main_thread_check()  # 检测主线程运行状态
        # 获取相簿
        try:
            album_response = get_album_page(album_id)
        except crawler.CrawlerException as e:
            self.error("相簿%s解析失败，原因：%s" % (album_id, e.message))
            raise

        self.trace("相簿%s解析的全部图片：%s" % (album_id, album_response["photo_url_list"]))
        self.step("相簿%s解析获取%s张图" % (album_id, len(album_response["photo_url_list"])))

        photo_index = 1
        for photo_url in album_response["photo_url_list"]:
            self.main_thread_check()  # 检测主线程运行状态
            self.step("相簿%s开始下载第%s张图片 %s" % (album_id, photo_index, photo_url))

            file_path = os.path.join(self.main_thread.photo_download_path, self.display_name, "%07d_%02d.%s" % (album_id, photo_index, net.get_file_type(photo_url, "jpg")))
            save_file_return = net.save_net_file(photo_url, file_path)
            if save_file_return["status"] == 1:
                self.step("相簿%s第%s张图片下载成功" % (album_id, photo_index))
                # 设置临时目录
                self.temp_path_list.append(file_path)
            else:
                self.error("相簿%s第%s张图片 %s，下载失败，原因：%s" % (album_id, photo_index, photo_url, crawler.download_failre(save_file_return["code"])))

        # 相簿内图片下全部载完毕
        self.temp_path_list = []  # 临时目录设置清除
        self.total_photo_count += photo_index - 1  # 计数累加
        self.account_info[1] = str(album_id)  # 设置存档记录

    def run(self):
        try:
            # 获取所有可下载日志
            album_id_list = self.get_crawl_list()
            self.step("需要下载的全部相簿解析完毕，共%s个" % len(album_id_list))

            # 从最早的相簿开始下载
            while len(album_id_list) > 0:
                album_id = album_id_list.pop()
                self.step("开始解析相簿%s" % album_id)
                self.crawl_album(album_id)
                self.main_thread_check()  # 检测主线程运行状态
        except SystemExit as se:
            if se.code == 0:
                self.step("提前退出")
            else:
                self.error("异常退出")
            # 如果临时目录变量不为空，表示某个相簿正在下载中，需要把下载了部分的内容给清理掉
            self.clean_temp_path()
        except Exception as e:
            self.error("未知异常")
            self.error(str(e) + "\n" + traceback.format_exc(), False)

        # 保存最后的信息
        with self.thread_lock:
            file.write_file("\t".join(self.account_info), self.main_thread.temp_save_data_path)
            self.main_thread.total_photo_count += self.total_photo_count
            self.main_thread.account_list.pop(self.account_id)
        self.step("下载完毕，总共获得%s张图片" % self.total_photo_count)
        self.notify_main_thread()


if __name__ == "__main__":
    BiliBili().main()