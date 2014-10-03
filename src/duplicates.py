# coding=utf-8
from logging import StreamHandler
import sys

__author__ = '4ikist'

import os
import logging
import datetime
from collections import defaultdict
import pickle
import re

log = logging.getLogger('main')
log.setLevel('DEBUG')
log.addHandler(StreamHandler(sys.stdout))

encoding = 'cp1251'  # sys.getdefaultencoding()

extensions = ['jpg', 'png', 'bmp', 'pdf', 'jpeg', 'ico', 'gif', 'tiff', 'svg',
              'txt', 'odt', 'fb2', 'djvu', 'doc', 'docx',
              'avi', 'mpg', 'mpeg', 'flv', 'mov', '3gp', 'mkv', 'wmv',
              'zip', 'rar', 'bz2', 'tar',
              'mp3', 'wav', 'aiff', ]

reg = re.compile(u"^(.*?)\W?((\(\d*\))|(copy\W?\d*)|( - копия\W?\d*)){0,999}$")
to_show = lambda x: x.decode(encoding)
retrieve_not_copy = lambda x: reg.findall(to_show(x))[0][0]


def get_excluded():
    excluded = defaultdict(list)
    excluded['files'] = []
    excluded['paths'] = []
    if os.path.isfile(os.path.join(os.getcwdu(), 'excluded')):
        with open(os.path.join(os.getcwdu(), 'excluded'), 'r') as f:
            try:
                excluded = pickle.load(f)
            except Exception as e:
                log.warn("excluded file is corrupted, i remove it...")
                os.remove(os.path.join(os.getcwdu(), 'excluded'))
    return excluded


def set_excluded(excluded):
    # log.info("saved excluded:\npaths:\n%s\n-----\nfiles:\n%s\n----" % (
    # to_show('\n'.join(excluded['paths'])), to_show('\n'.join(excluded['files']))))
    with open(os.path.join(os.getcwdu(), 'excluded'), 'w+') as f:
        pickle.dump(excluded, f)


def remove_excluded(dir_names, excluded_paths):
    cur_excluded = []
    for dir_name in dir_names:
        if dir_name in excluded_paths:
            cur_excluded.append(dir_name)
    for excluded_dir in cur_excluded:
        dir_names.remove(excluded_dir)


def get_intersection_of_path(paths):
    base = paths[0]
    i = 0
    while i <= len(paths) - 1:
        if base not in paths[i]:
            base, _ = os.path.split(base)
            i = -1
        i += 1
    return base


def is_similar_size(attrs):
    prev_size = 0
    for el in attrs:
        if prev_size != 0 and prev_size == el['size']:
            return True
        prev_size = el['size']
    return False


def get_longest_path(attrs):
    paths_with_length = dict([(len(p['path']), p['path']) for p in attrs])
    lengths = paths_with_length.keys()
    lengths.sort()
    return paths_with_length[lengths[-1]], len(paths_with_length)


def process_duplicates(files, quite=False):
    excluded = get_excluded()
    for fn, attrs in files.iteritems():
        if len(attrs) > 1 and is_similar_size(attrs):
            path = get_intersection_of_path([el['path'] for el in attrs])
            if path in excluded['paths'] or fn.encode(encoding) in excluded['files']:
                continue

            log.info('\n\nFile: %s \nin: \n%s\n---' % (
                to_show(fn),
                '\n'.join(
                    ['%s) %s [%s][%s]' % (i, to_show(os.path.join(el['path'], el['fn'])), el['size'], el['created_at'])
                     for i, el in
                     enumerate(attrs)])))
            while 1:
                if quite:
                    # retain file with not copy postfix or with longest path
                    longest, count_different = get_longest_path(attrs)
                    for el in attrs:
                        if fn.encode(encoding) != os.path.splitext(el['fn'])[0] or (
                                        count_different > 1 and el['path'] != longest):
                            what_remove = os.path.join(el['path'], el['fn'])
                            log.info('remove %s ' % to_show(what_remove))
                            os.remove(what_remove)
                    break
                else:
                    command = raw_input(
                        'what you want? exclude this path - ep, exclude this file - ef, retain only with path number - r<number>, next - n\n')
                    if command == 'ep':
                        log.info('will exclude this path: %s\n' % to_show(path))
                        excluded['paths'].append(path)
                    elif command == 'ef':
                        excluded['files'].append(fn)
                    elif 'r' in command:
                        try:
                            retain_index = int(command[1:])
                        except ValueError:
                            log.error("i can not recognise index of this command [%s], try another index" % command)
                            continue
                        if retain_index >= len(attrs):
                            log.error("index in this command [%s] is invalid, try another index" % command)
                            continue
                        for i, el in enumerate(attrs):
                            if i != retain_index:
                                log.info('will remove: %s in %s' % (to_show(el['fn']), to_show(el['path'])))
                                confirm = raw_input('confirm? y/n')
                                if confirm.lower() == 'y':
                                    os.remove(os.path.join(el['path'], el['fn']))
                    break

    set_excluded(excluded)


def get_files(start_path):
    """
    return {file_name:[{path:..., size:...,created_at:...},..]}
    :param start_path:
    :return:
    """
    excluded = get_excluded()
    result = defaultdict(list)
    log.info("found duplicates...")
    for dir_path, dir_names, filenames in os.walk(start_path):
        remove_excluded(dir_names, excluded['paths'])
        for filename in filenames:
            full_filename = os.path.join(dir_path, filename)
            _, extension = os.path.splitext(full_filename)
            if extension.lower()[1:] in extensions and filename not in excluded['files']:
                try:
                    stat = os.stat(full_filename)
                except WindowsError as e:
                    excluded['files'].append(filename)
                    continue
                size, access_time, modification_time, metadata_change_time = stat[-4:]
                access_time = datetime.datetime.fromtimestamp(access_time)
                modification_time = datetime.datetime.fromtimestamp(modification_time)
                try:
                    result[retrieve_not_copy(os.path.splitext(filename)[0])].append(
                        {'path': dir_path, 'size': size, 'created_at': access_time, 'modified_at': modification_time,
                         'fn': filename})
                except UnicodeDecodeError as e:
                    log.error("can not process filename: %s" % filename)
    log.info("duplicates was found...")
    set_excluded(excluded)

    return result


if __name__ == '__main__':
    root = sys.argv[1]
    if len(sys.argv) == 3:
        quite = True
    else:
        quite = False
    if not os.path.isdir(root):
        log.error("%s is not dir" % root)
    process_duplicates(get_files(root), quite=quite)