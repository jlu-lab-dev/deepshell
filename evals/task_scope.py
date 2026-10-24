"""Derive a v3 object contract from declared operations, never from a task ID."""
from copy import deepcopy
import ntpath

from evals.agent_state import contract_for, path
from sys_agent.object_access import ObjectScope

ROOT = r'D:\AgentEvalSandbox'
PATH_FIELDS = frozenset({'path', 'src', 'dst', 'image_path', 'attachment_path'})


def effect_paths(tool, args):
    if tool in {'find_file','find_files_by_extension','find_path_by_keywords'}:
        return []
    if tool == 'create_text_file':
        return [ntpath.join(ROOT, 'workspace', args['filename'])]
    if tool == 'save_text_as_word_doc':
        return [ntpath.join(args['directory'], args['filename'])]
    if tool == 'create_directory':
        return [ntpath.join(args.get('base_directory', ''), args['path'])]
    values = [v for k, v in args.items() if k in PATH_FIELDS and v]
    if 'file_paths' in args:
        values += args['file_paths']
        values += batch_destinations(tool, args)
    return values


def batch_destinations(tool, args):
    result = []
    for i, source in enumerate(args.get('file_paths', [])):
        if tool == 'batch_move_files':
            target = ntpath.join(args['destination_directory'], ntpath.basename(source))
        elif tool == 'batch_add_prefix_to_filenames':
            target = ntpath.join(ntpath.dirname(source), args['prefix'] + ntpath.basename(source))
        elif tool == 'batch_rename_files':
            target = ntpath.join(ntpath.dirname(source), args['rename_pattern'].format(num=args.get('start_number', 1)+i) + ntpath.splitext(source)[1])
        else:
            continue
        result.append(target)
    return result


def contract_v3(steps, *, initial_files=None):
    contract = contract_for(steps)
    contract.update(version=3, root=ROOT, initial_files=deepcopy(initial_files or {}),
                    read_limits={'max_read_calls':16, 'max_file_bytes':16384,
                                 'max_result_bytes':32768, 'max_total_result_bytes':131072, 'max_results':16})
    contract['verification'] = {'objects_before_and_after':True, 'scoped_lookup_only':True}
    return contract


def make_scope(contract, initial_files):
    objects = set()
    for step in contract['operations']:
        tool, args = step['tool'], step['args']
        objects.update(effect_paths(tool, args))
        # An explicitly requested query defines its own search objective. Extra
        # model queries never expand this frozen scope or inspect ambient files.
        if tool == 'find_file':
            directory, term = path(args.get('path', ROOT)), args['filename'].casefold()
            objects.update(p for p in initial_files if ntpath.commonpath([directory,p])==directory and term in ntpath.basename(p).casefold())
        elif tool == 'find_files_by_extension':
            directory = path(args['directory'])
            objects.update(p for p in initial_files if ntpath.commonpath([directory,p])==directory and ntpath.splitext(p)[1] in args['extensions'])
        elif tool == 'find_path_by_keywords':
            directory = path(args['search_directory'])
            objects.update(p for p in initial_files if ntpath.commonpath([directory,p])==directory and all(t.casefold() in p.casefold() for t in args['keywords']))
    return ObjectScope(root=contract['root'], objects=frozenset(objects), **contract['read_limits'])
