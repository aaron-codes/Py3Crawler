# -*- coding:UTF-8  -*-
"""
尊光图片爬虫
http://zunguang.com/
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
import os
from common import *

ERROR_PAGE_COUNT_CHECK = 10


# 根据页面内容获取图片地址列表
def get_album_page(page_count):
    album_url = "http://www.zunguang.com/index.php?c=api&yc=blog&ym=getOneBlog"
    post_data = {"bid": page_count}
    album_response = net.http_request(album_url, method="POST", fields=post_data, json_decode=True, is_random_ip=False)
    result = {
        "album_title": "",  # 相册标题
        "photo_url_list": [],  # 全部图片地址
        "is_skip": False,  # 是否需要跳过（没有内容，不需要下载）
    }
    if album_response.status != net.HTTP_RETURN_CODE_SUCCEED:
        raise crawler.CrawlerException(crawler.request_failre(album_response.status))
    if not crawler.check_sub_key(("body",), album_response.json_data):
        raise crawler.CrawlerException("返回数据'body'字段不存在\n%s" % album_response.json_data)
    if not crawler.check_sub_key(("blog",), album_response.json_data["body"]):
        raise crawler.CrawlerException("返回数据'blog'字段不存在\n%s" % album_response.json_data)
    # 判断是不是需要跳过
    if album_response.json_data["body"]["blog"] is False:
        result["is_skip"] = True
    else:
        if not isinstance(album_response.json_data["body"]["blog"], list):
            raise crawler.CrawlerException("返回数据'blog'字段类型不正确\n%s" % album_response.json_data)
        if len(album_response.json_data["body"]["blog"]) != 1:
            raise crawler.CrawlerException("返回数据'blog'字段长度不正确\n%s" % album_response.json_data)
        if not crawler.check_sub_key(("type",), album_response.json_data["body"]["blog"][0]):
            raise crawler.CrawlerException("返回数据'type'字段不存在\n%s" % album_response.json_data)
        # 获取相册类型
        album_type = int(album_response.json_data["body"]["blog"][0]["type"])
        if album_type not in [2, 3]:
            raise crawler.CrawlerException("返回数据'type'字段取值不正确\n%s" % album_response.json_data)
        if album_type == 2:  # 歌曲类型的相册
            result["is_skip"] = True
        elif album_type == 3:  # 图片类型的相册
            album_body = album_response.json_data["body"]["blog"][0]
            # 获取相册标题
            if not crawler.check_sub_key(("title",), album_body):
                raise crawler.CrawlerException("返回数据'title'字段不存在\n%s" % album_response.json_data)
            result["album_title"] = album_body["title"]
            # 获取图片地址
            if not crawler.check_sub_key(("attr",), album_body):
                raise crawler.CrawlerException("返回数据'attr'字段不存在\n%s" % album_response.json_data)
            if not crawler.check_sub_key(("img",), album_body["attr"]):
                raise crawler.CrawlerException("返回数据'img'字段不存在\n%s" % album_response.json_data)
            if len(album_body["attr"]["img"]) == 0:
                raise crawler.CrawlerException("返回数据'img'字段长度不正确\n%s" % album_response.json_data)
            for photo_data in album_body["attr"]["img"]:
                if not crawler.check_sub_key(("url",), photo_data):
                    raise crawler.CrawlerException("返回数据'url'字段不存在\n%s" % album_response.json_data)
                result["photo_url_list"].append("http://www.zunguang.com/%s" % photo_data["url"])
    return result


class ZunGuang(crawler.Crawler):
    def __init__(self, **kwargs):
        # 设置APP目录
        crawler.PROJECT_APP_PATH = os.path.abspath(os.path.dirname(__file__))

        # 初始化参数
        sys_config = {
            crawler.SYS_DOWNLOAD_PHOTO: True,
            crawler.SYS_NOT_CHECK_SAVE_DATA: True,
        }
        crawler.Crawler.__init__(self, sys_config, **kwargs)

        output.print_msg("配置文件读取完成")

    def main(self):
        # 解析存档文件，获取上一次的page count
        if os.path.exists(self.save_data_path):
            page_count = int(file.read_file(self.save_data_path))
        else:
            page_count = 1

        error_count = 0
        is_over = False
        while not is_over:
            if not self.is_running():
                tool.process_exit(0)
            log.step("开始解析第%s页图片" % page_count)

            # 获取相册
            try:
                album_response = get_album_page(page_count)
            except crawler.CrawlerException as e:
                log.error("第%s页相册解析失败，原因：%s" % (page_count, e.message))
                page_count -= error_count
                break
            except SystemExit:
                log.step("提前退出")
                page_count -= error_count
                break

            if album_response["is_skip"]:
                error_count += 1
                if error_count >= ERROR_PAGE_COUNT_CHECK:
                    log.error("连续%s页相册没有图片，退出程序" % ERROR_PAGE_COUNT_CHECK)
                    page_count -= error_count - 1
                    break
                else:
                    log.error("第%s页相册没有图片，跳过" % page_count)
                    page_count += 1
                    continue

            # 错误数量重置
            error_count = 0

            # 下载目录标题
            # 过滤标题中不支持的字符
            album_title = path.filter_text(album_response["album_title"])
            if album_title:
                photo_path = os.path.join(self.photo_download_path, "%04d %s" % (page_count, album_title))
            else:
                photo_path = os.path.join(self.photo_download_path, "%04d" % page_count)

            log.trace("第%s页相册解析的全部图片：%s" % (page_count, album_response["photo_url_list"]))
            photo_count = 1
            for photo_url in album_response["photo_url_list"]:
                if not self.is_running():
                    tool.process_exit(0)
                log.step("开始下载第%s页第%s张图片 %s" % (page_count, photo_count, photo_url))

                file_path = os.path.join(photo_path, "%03d.%s" % (photo_count, net.get_file_type(photo_url)))
                try:
                    save_file_return = net.save_net_file(photo_url, file_path, need_content_type=True)
                    if save_file_return["status"] == 1:
                        log.step("第%s页第%s张图片下载成功" % (page_count, photo_count))
                        photo_count += 1
                    else:
                        log.error("第%s页第%s张图片 %s 下载失败，原因：%s" % (page_count, photo_count, photo_url, crawler.download_failre(save_file_return["code"])))
                except SystemExit:
                    log.step("提前退出")
                    path.delete_dir_or_file(photo_path)
                    is_over = True
                    break

            if not is_over:
                self.total_photo_count += photo_count - 1
                page_count += 1

        # 重新保存存档文件
        if self.total_photo_count > 0:
            file.write_file(str(page_count), self.save_data_path, file.WRITE_FILE_TYPE_REPLACE)

        log.step("全部下载完毕，耗时%s秒，共计图片%s张" % (self.get_run_time(), self.total_photo_count))


if __name__ == "__main__":
    ZunGuang().main()
