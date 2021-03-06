# -*- coding:UTF-8  -*-
"""
xvideos视频爬虫
https://www.xvideos.com/
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
import os
import re
import time
import traceback
from pyquery import PyQuery as pq
from common import *

COOKIE_INFO = {}
VIDEO_QUALITY = 2
ACTION_WHEN_BLOCK_HD_QUALITY = 2
CATEGORY_WHITELIST = ""
CATEGORY_BLACKLIST = ""


# 获取指定视频
def get_video_page(video_id):
    video_play_url = "https://www.xvideos.com/video%s/" % video_id
    # 强制使用英语
    video_play_response = net.http_request(video_play_url, method="GET")
    result = {
        "is_delete": False,  # 是否已删除
        "is_skip": False,  # 是否跳过
        "video_title": "",  # 视频标题
        "video_url": None,  # 视频地址
    }
    if video_play_response.status == 404 or video_play_response.status == 403:
        result["is_delete"] = True
        return result
    if video_play_response.status != net.HTTP_RETURN_CODE_SUCCEED:
        raise crawler.CrawlerException(crawler.request_failre(video_play_response.status))
    video_play_response_content = video_play_response.data.decode(errors="ignore")
    # 过滤视频category
    category_list_selector = pq(video_play_response_content).find(".video-tags-list ul li a")
    category_list = []
    for category_index in range(1, category_list_selector.length):
        category_selector = category_list_selector.eq(category_index)
        category_list.append(category_selector.html().strip().lower())
    if CATEGORY_BLACKLIST or CATEGORY_WHITELIST:
        is_skip = True if CATEGORY_WHITELIST else False
        for category in category_list:
            if CATEGORY_BLACKLIST:
                # category在黑名单中
                if len(re.findall(CATEGORY_BLACKLIST, category)) > 0:
                    is_skip = True
                    break
            if CATEGORY_WHITELIST:
                # category在黑名单中
                if len(re.findall(CATEGORY_WHITELIST, category)) > 0:
                    is_skip = False
        if is_skip:
            result["is_skip"] = True
            return result
    # 获取视频标题
    video_title = tool.find_sub_string(video_play_response_content, "html5player.setVideoTitle('", "');")
    if not video_title:
        raise crawler.CrawlerException("页面截取视频标题失败\n%s" % video_play_response_content)
    result["video_title"] = video_title.strip()
    # 获取视频地址
    if VIDEO_QUALITY == 2:
        video_url = tool.find_sub_string(video_play_response_content, "html5player.setVideoUrlHigh('", "');")
        # 被屏蔽了高质量视频
        if not video_url:
            if ACTION_WHEN_BLOCK_HD_QUALITY == 1:
                video_url = tool.find_sub_string("html5player.setVideoUrlLow('", "');")
            elif ACTION_WHEN_BLOCK_HD_QUALITY == 2:
                log.error("高质量视频地址已被暂时屏蔽，等待10分钟")
                time.sleep(600)
                return get_video_page(video_id)
            else:
                raise crawler.CrawlerException("高质量视频地址已被暂时屏蔽")
    else:
        video_url = tool.find_sub_string("html5player.setVideoUrlLow('", "');")
    # if not video_url:
    #     video_info_url = "https://www.xvideos.com/video-download/%s" % video_id
    #     video_info_response = net.http_request(video_info_url, method="GET", cookies_list=COOKIE_INFO, json_decode=True)
    #     if video_info_response.status != net.HTTP_RETURN_CODE_SUCCEED:
    #         raise crawler.CrawlerException("视频下载请求，" + crawler.request_failre(video_info_response.status))
    #     if VIDEO_QUALITY == 2:
    #         if not crawler.check_sub_key(("URL",), video_info_response.json_data):
    #             raise crawler.CrawlerException("视频下载信息，'URL'字段不存在\n%s" % video_info_response.json_data)
    #         video_url = video_info_response.json_data["URL"]
    #     else:
    #         if not crawler.check_sub_key(("URL_LOW",), video_info_response.json_data):
    #             raise crawler.CrawlerException("视频下载信息，'URL_LOW'字段不存在\n%s" % video_info_response.json_data)
    #         video_url = video_info_response.json_data["URL_LOW"]
    if not video_url:
        raise crawler.CrawlerException("页面截取视频地址失败\n%s" % video_play_response_content)
    result["video_url"] = video_url
    return result


class XVideos(crawler.Crawler):
    def __init__(self, **kwargs):
        global COOKIE_INFO
        global VIDEO_QUALITY
        global ACTION_WHEN_BLOCK_HD_QUALITY
        global CATEGORY_WHITELIST
        global CATEGORY_BLACKLIST

        # 设置APP目录
        crawler.PROJECT_APP_PATH = os.path.abspath(os.path.dirname(__file__))

        # 初始化参数
        sys_config = {
            crawler.SYS_DOWNLOAD_VIDEO: True,
            crawler.SYS_SET_PROXY: True,
            crawler.SYS_NOT_CHECK_SAVE_DATA: True,
            crawler.SYS_GET_COOKIE: ("xvideos.com",),
            crawler.SYS_APP_CONFIG: (
                ("VIDEO_QUALITY", 2, crawler.CONFIG_ANALYSIS_MODE_INTEGER),
                ("ACTION_WHEN_BLOCK_HD_QUALITY", 2, crawler.CONFIG_ANALYSIS_MODE_INTEGER),
                ("CATEGORY_WHITELIST", "", crawler.CONFIG_ANALYSIS_MODE_RAW),
                ("CATEGORY_BLACKLIST", "", crawler.CONFIG_ANALYSIS_MODE_RAW),
            ),
        }
        crawler.Crawler.__init__(self, sys_config, **kwargs)

        # 设置全局变量，供子线程调用
        COOKIE_INFO = self.cookie_value
        VIDEO_QUALITY = self.app_config["VIDEO_QUALITY"]
        if VIDEO_QUALITY not in [1, 2]:
            VIDEO_QUALITY = 2
            log.error("配置文件config.ini中key为'video_quality'的值必须是1或2，使用程序默认设置")

        ACTION_WHEN_BLOCK_HD_QUALITY = self.app_config["ACTION_WHEN_BLOCK_HD_QUALITY"]
        if ACTION_WHEN_BLOCK_HD_QUALITY not in [1, 2, 3]:
            ACTION_WHEN_BLOCK_HD_QUALITY = 2
            log.error("配置文件config.ini中key为'ACTION_WHEN_BLOCK_HD_QUALITY'的值必须是1至3之间的整数，使用程序默认设置")

        category_whitelist = self.app_config["CATEGORY_WHITELIST"]
        if category_whitelist:
            CATEGORY_WHITELIST = "|".join(category_whitelist.lower().split(",")).replace("*", "\w*")
        category_blacklist = self.app_config["CATEGORY_BLACKLIST"]
        if category_blacklist:
            CATEGORY_BLACKLIST = "|".join(category_blacklist.lower().split(",")).replace("*", "\w*")

    def main(self):
        # 解析存档文件，获取上一次的album id
        video_id = 1
        if os.path.exists(self.save_data_path):
            file_save_info = file.read_file(self.save_data_path)
            if not crawler.is_integer(file_save_info):
                log.error("存档内数据格式不正确")
                tool.process_exit()
            video_id = int(file_save_info)

        try:
            while video_id:
                if not self.is_running():
                    tool.process_exit(0)
                log.step("开始解析视频%s" % video_id)

                # 获取视频
                try:
                    video_play_response = get_video_page(video_id)
                except crawler.CrawlerException as e:
                    log.error("视频%s解析失败，原因：%s" % (video_id, e.message))
                    raise

                if video_play_response["is_delete"]:
                    log.step("视频%s已删除，跳过" % video_id)
                    video_id += 1
                    continue

                if video_play_response["is_skip"]:
                    log.step("视频%s已过滤，跳过" % video_id)
                    video_id += 1
                    continue

                log.step("开始下载视频%s《%s》 %s" % (video_id, video_play_response["video_title"], video_play_response["video_url"]))
                file_path = os.path.join(self.video_download_path, "%08d %s.mp4" % (video_id, path.filter_text(video_play_response["video_title"])))
                save_file_return = net.save_net_file(video_play_response["video_url"], file_path, head_check=True)
                if save_file_return["status"] == 1:
                    log.step("视频%s《%s》 下载成功" % (video_id, video_play_response["video_title"]))
                else:
                    log.error("视频%s《%s》 %s 下载失败，原因：%s" % (video_id, video_play_response["video_title"], video_play_response["video_url"], crawler.download_failre(save_file_return["code"])))

                # 视频下载完毕
                self.total_video_count += 1  # 计数累加
                video_id += 1  # 设置存档记录
        except SystemExit as se:
            if se.code == 0:
                log.step("提前退出")
            else:
                log.error("异常退出")
        except Exception as e:
            log.error("未知异常")
            log.error(str(e) + "\n" + traceback.format_exc())

        # 重新保存存档文件
        file.write_file(str(video_id), self.save_data_path, file.WRITE_FILE_TYPE_REPLACE)
        log.step("全部下载完毕，耗时%s秒，共计视频%s个" % (self.get_run_time(), self.total_video_count))


if __name__ == "__main__":
    XVideos().main()
