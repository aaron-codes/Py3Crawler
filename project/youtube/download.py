# -*- coding:UTF-8  -*-
"""
指定Youtube视频下载
https://www.youtube.com
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
import os
from common import *
from project.youtube import youtube

DOWNLOAD_FILE_PATH = os.path.join(os.path.dirname(__file__), "video")


def main():
    config = crawler._get_config()
    # 获取cookies
    all_cookie_from_browser = crawler.quickly_get_all_cookies_from_browser(config)
    if "youtube.com" in all_cookie_from_browser:
        for cookie_key in all_cookie_from_browser["youtube.com"]:
            youtube.COOKIE_INFO[cookie_key] = all_cookie_from_browser["youtube.com"][cookie_key]
    if ".youtube.com" in all_cookie_from_browser:
        for cookie_key in all_cookie_from_browser[".youtube.com"]:
            youtube.COOKIE_INFO[cookie_key] = all_cookie_from_browser[".youtube.com"][cookie_key]
    if len(youtube.COOKIE_INFO) == 0 or not youtube.check_login():
        output.print_msg("没有检测到登录信息", False)
        youtube.IS_LOGIN = False
    # 设置代理
    crawler.quickly_set_proxy(config)

    while True:
        video_url = input("请输入youtube视频地址：")
        video_id = None
        # https://www.youtube.com/watch?v=lkHlnWFnA0c
        if video_url.lower().find("//www.youtube.com/") > 0:
            query_string_list = video_url.split("?")[-1].split("&")
            for query_string in query_string_list:
                if query_string.find("=") == -1:
                    continue
                key, value = query_string.split("=", 1)
                if key == "v":
                    video_id = value
        # https://youtu.be/lkHlnWFnA0c
        elif video_url.lower().find("//youtu.be/") > 0:
            video_id = video_url.split("/")[-1].split("&")[0]
        # 无效的视频地址
        if video_id is None:
            output.print_msg("错误的视频地址，正确的地址格式为：https://www.youtube.com/watch?v=lkHlnWFnA0c 或 https://youtu.be/lkHlnWFnA0c", False)
            continue
        # 访问视频播放页
        try:
            video_response = youtube.get_video_page(video_id)
        except crawler.CrawlerException as e:
            output.print_msg("解析视频下载地址失败，原因：%s" % e.message, False)
        # 开始下载
        video_file_path = os.path.abspath(os.path.join(DOWNLOAD_FILE_PATH, "%s - %s.mp4" % (video_id, path.filter_text(video_response["video_title"]))))
        output.print_msg("解析出的视频标题：%s\n视频地址：%s\n下载路径：%s" % (video_response["video_title"], video_response["video_url"], video_file_path), False)
        save_file_return = net.save_net_file(video_response["video_url"], video_file_path, head_check=True)
        if save_file_return["status"] == 1:
            # 设置临时目录
            output.print_msg("视频《%s》下载成功" % video_response["video_title"], False)
        else:
            output.print_msg("视频《%s》下载失败，原因：%s" % (video_response["video_title"], crawler.download_failre(save_file_return["code"])), False)


if __name__ == "__main__":
    main()