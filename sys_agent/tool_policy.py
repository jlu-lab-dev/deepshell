"""Explicit GUI tool policy. The historical benchmark retains its four-tool profile."""

READ_ONLY_TOOL_NAMES = frozenset({
    'get_current_directory', 'get_user_folder_path', 'list_running_applications',
    'list_applications_by_memory_usage', 'read_file', 'read_table_data',
    'find_file', 'find_files_by_extension', 'find_path_by_keywords', 'get_contact_email',
})

APPROVAL_EFFECTS = {
    'open_file': '用系统关联程序打开文件；可执行文件可能启动程序。',
    'create_file': '在指定路径创建文件和所需目录；不覆盖已有文件。',
    'write_file': '写入指定文件，已有内容将被覆盖。',
    'rename_file': '重命名文件；目标已存在时可能覆盖或失败。',
    'copy_file': '复制文件；目标已存在时可能覆盖。',
    'move_file': '移动文件或目录；目标已存在时可能覆盖或失败。',
    'batch_move_files': '移动所列文件或目录；目标已存在时可能覆盖或失败。',
    'create_directory': '在指定位置创建目录。',
    'delete_file': '永久删除指定文件，不经过回收站。',
    'save_text_as_word_doc': '保存 Word 文档；已有同名文档将被覆盖。',
    'clean_system_cache': '永久清理预览列出的缓存项；目录内的内容也将删除，正在使用的项可能失败。',
    'batch_rename_files': '按编号模式重命名所列文件，可能覆盖已有目标或失败。',
    'batch_add_prefix_to_filenames': '为所列文件添加前缀，可能覆盖已有目标或失败。',
    'open_calculator': '启动计算器。',
    'shutdown_system': '关闭本机；请先保存所有未保存的工作。',
    'run_program': '通过系统 Shell 执行完整命令；命令可修改文件、启动程序或访问网络。',
    'set_wallpaper': '更改桌面壁纸。',
    'open_control_panel': '打开控制面板。',
    'open_network_settings': '打开网络设置。',
    'open_display_settings': '打开显示设置。',
    'open_sound_settings': '打开声音设置。',
    'open_bluetooth_settings': '打开蓝牙设置。',
    'lock_screen': '锁定当前屏幕。',
    'close_application_by_name': '终止所有匹配名称的应用进程，未保存的数据可能丢失。',
    'close_application_by_pid': '终止指定 PID 的进程，未保存的数据可能丢失。',
    'open_task_manager': '打开任务管理器。',
    'open_browser': '打开默认浏览器。',
    'search_in_browser': '在默认浏览器中把查询发送到所选搜索引擎。',
    'compose_email': '打开默认邮件客户端的草稿；不会自动发信，附件须在客户端手动添加。',
    'generate_report_text': '将表格数据和要求发送给当前 Agent 所选模型生成报告。',
}

ALL_TOOL_NAMES = READ_ONLY_TOOL_NAMES | frozenset(APPROVAL_EFFECTS)


def freeze_paths(tool_name, arguments):
    """Resolve path arguments before approval so changing cwd cannot redirect execution."""
    import os
    from copy import deepcopy
    args = deepcopy(arguments)
    path_fields = {'path', 'src', 'dst', 'directory', 'destination_directory',
                   'base_directory', 'search_directory', 'image_path', 'attachment_path'}
    if tool_name == 'create_directory' and args.get('base_directory'):
        args['path'] = os.path.join(os.path.expanduser(args['base_directory']), args['path'])
        args.pop('base_directory')
    for field in path_fields & args.keys():
        if args[field]:
            args[field] = os.path.abspath(os.path.expanduser(args[field]))
    if 'file_paths' in args:
        args['file_paths'] = [os.path.abspath(os.path.expanduser(path)) for path in args['file_paths']]
    return args
