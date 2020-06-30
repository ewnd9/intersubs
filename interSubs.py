#! /usr/bin/env python

# v. 2.7
# Interactive subtitles for `mpv` for language learners.

import os
import sys
import queue
from PyQt5.QtWidgets import QApplication
import interSubs_config as config
from interSubs_ui import main_class

pth = os.path.expanduser('~/.config/mpv/scripts/')
os.chdir(pth)

if __name__ == "__main__":
    print('[py part] Starting interSubs ...')

    try:
        os.mkdir('urls')
    except BaseException:
        pass

    if 'tab_divided_dict' in config.translation_function_names:
        offdict = {x.split('\t')[0].strip().lower(): x.split('\t')[1].strip() for x in open(
            os.path.expanduser(config.tab_divided_dict_fname)).readlines() if '\t' in x}

    app = QApplication(sys.argv)

    config.avoid_resuming = False
    config.block_popup = False
    config.scroll = {}
    config.queue_to_translate = queue.Queue()
    config.screen_width = app.primaryScreen().size().width()
    config.screen_height = app.primaryScreen().size().height()

    config.mpv_socket = sys.argv[1]
    config.sub_file = sys.argv[2]
    config.subs = ''

    form = main_class()
    app.exec_()
