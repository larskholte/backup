#!/usr/bin/python3

from pathlib import Path
from os.path import join, islink
from os import chown, link, symlink, mkdir, remove as rm
from shutil import copy2, copystat, rmtree
from stat import S_ISDIR

def conflict(*members):
    print('More than one difference among the following:')
    for mem in members:
        # TODO: make nice informative output
        print('\t'+str(mem))

def equal(*srcs,**opts):
    '''Compares the given Paths non-recursively for equality.'''
    if len(srcs) == 0 or len(srcs) == 1: return True
    num_exist = 0
    for src in srcs:
        if src.exists(): num_exist += 1
    # Sets of non-existent files are equal
    if num_exist == 0: return True
    # All must exist or none
    if num_exist != len(srcs): return False
    # All exist
    stats = [ src.lstat() for src in srcs ]
    mode  = stats[0].st_mode
    uid   = stats[0].st_uid
    gid   = stats[0].st_gid
    size  = stats[0].st_size
    mtime = stats[0].st_mtime
    # Compare all stats for equality
    for stat in stats[1:]:
        if stat.st_mode != mode: return False
        if stat.st_uid != uid and not bool(opts.get('iuid')): return False
        if stat.st_gid != gid and not bool(opts.get('igid')): return False
        if stat.st_size != size and not S_ISDIR(mode): return False
        if stat.st_mtime != mtime and (not S_ISDIR(stat.st_mode) or not bool(opts.get('idt'))): return False
    return True

def place(src,dest,**opts):
    '''Copies the given (extant) source file to the given (non-extant) destination file, using the given options. Does not work with directories.'''
    src_stat = src.lstat()
    dest_stat = dest.parent.lstat()
    if src_stat.st_dev == dest_stat.st_dev and not islink(str(src)) and bool(opts.get('hl')):
        print('link',src,dest)
        link(str(src),str(dest),follow_symlinks=False)
    else:
        if islink(str(src)): print('copylink',src,dest)
        else: print('copy',src,dest)
        copy2(str(src),str(dest),follow_symlinks=False)
        if bool(opts.get('chown')): chown(str(dest),src_stat.st_uid,src_stat.st_gid,follow_symlinks=False)

def strongcopy(src,dest,**opts):
    '''Copies the given (extant) source file or directory recursively to the given (non-extant) destination using the given options.'''
    src_stat = src.lstat()
    if not S_ISDIR(src_stat.st_mode): # src is a file
        place(src,dest,**opts)
        return
    # src is a directory
    mkdir(str(dest))
    copystat(str(src),str(dest),follow_symlinks=False)
    if bool(opts.get('chown')): chown(str(dest),src_stat.st_uid,src_stat.st_gid,follow_symlinks=False)
    s = set()
    for c in src.iterdir(): s.add(c.name)
    for c in s: strongcopy(src/c,dest/c,**opts)

def replace(src,dest,**opts):
    '''Copies the given (possibly non-extant) source to the given (possibly non-extant) destination preserving mode, modification time, and ownership using the given options. If the source is a directory, the replacement is applied recursively. Files that are in the destination but not in the source are removed. The destination must be inside an extant directory.'''
    if opts.get('exclude') and src in opts.get('exclude'): return
    if not src.exists():
        if not dest.exists(): return
        # Destination must be removed
        dest_stat = dest.lstat()
        if S_ISDIR(dest_stat.st_mode): rmtree(str(dest))
        else: rm(str(dest))
        return
    # src exists
    if not dest.exists():
        strongcopy(src,dest,**opts)
        return
    # src and dest both exist
    src_stat = src.lstat()
    dest_stat = dest.lstat()
    if not S_ISDIR(src_stat.st_mode):
        # src is a file
        if S_ISDIR(dest_stat.st_mode):
            rmtree(str(dest))
            strongcopy(src,dest,**opts)
            return
        if equal(src,dest,**opts): return
        # src and dest are unequal files
        rm(str(dest))
        strongcopy(src,dest,**opts)
        return
    # src is a directory
    if not S_ISDIR(dest_stat.st_mode):
        rm(str(dest))
        strongcopy(src,dest,**opts)
        return
    # src and dest are both directories
    if not equal(src,dest,**opts):
        src_stat = src.lstat()
        copystat(str(src),str(dest),follow_symlinks=False)
        if bool(opts.get('chown')): chown(str(dest),src_stat.st_uid,src_stat.st_gid,follow_symlinks=False)
    # src and dest are equal directories
    s = set()
    for c in src.iterdir(): s.add(c.name)
    for c in dest.iterdir(): s.add(c.name)
    for c in s:
        replace(src/c,dest/c,**opts)

def merge(ref,dest,*srcs,**opts):
    '''Merges the given sources into the given destination using the given reference. The destination should not exist, but should be in a directory that does exist. One or more of the reference and the listed sources should exist. The reference and destination must be on the same drive if they are to be hard linked.'''
    if len(srcs) == 0:
        ref_stat = ref.lstat()
        if not S_ISDIR(ref_stat.st_mode):
            place(ref,dest,**opts)
            return
        mkdir(str(dest))
        copystat(str(ref),str(dest),follow_symlinks=False)
        stat = ref.lstat()
        if bool(opts.get('chown')): chown(str(dest),stat.st_uid,stat.st_gid,follow_symlinks=False)
        s = set()
        for c in ref.iterdir(): s.add(c.name)
        for c in s: merge(ref/c,dest/c,**opts)
        return
    if equal(ref,*srcs,**opts):
        # ref and sources are all equal
        ref_stat = ref.lstat()
        if not S_ISDIR(ref_stat.st_mode):
            place(ref,dest,**opts)
            return
        # ref and sources are all directories
        mkdir(str(dest))
        copystat(str(ref),str(dest),follow_symlinks=False)
        stat = ref.lstat()
        if bool(opts.get('chown')): chown(str(dest),stat.st_uid,stat.st_gid,follow_symlinks=False)
        s = set()
        for c in ref.iterdir(): s.add(c.name)
        for src in srcs:
            for c in src.iterdir(): s.add(c.name)
        for c in s: merge(ref/c,dest/c,*[src/c for src in srcs],**opts)
        return
    # Reference is not equal to all sources
    # See if there has been more than one change among all the sources
    unequal = None
    for src in srcs: # Find the first source different from the reference
        if equal(src,ref,**opts): continue
        unequal = src
        break
    for src in srcs:
        if equal(src,ref,**opts): continue
        if equal(src,unequal,**opts): continue
        conflict(ref,*srcs)
        return
    # There has been only one change from the reference among all the sources
    # This does not necessarily mean only one source has changed
    replace(unequal,dest,**opts)

if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('command',help='Command',choices=['merge','replace','equal'])
    parser.add_argument('reference',help='Reference tree')
    parser.add_argument('destination',help='Destination tree (should not exist)')
    parser.add_argument('sources',help='Trees to merge',nargs='*')
    parser.add_argument('--exclude',help='Trees to exclude',action='append')
    parser.add_argument('--ignore-directory-timestamps',dest='idt',help='Consider directories with different timestamps that are otherwise identical equal (default).',action='store_true')
    parser.add_argument('--no-ignore-directory-timestamps',dest='idt',action='store_false')
    parser.add_argument('--hard-link',dest='hl',help='Hard-link files if possible (default).',action='store_true')
    parser.add_argument('--no-hard-link',dest='hl',action='store_false')
    parser.add_argument('--ignore-uid',dest='iuid',help='Consider files and directories with different user IDs that are otherwise identical equal (not default).',action='store_true')
    parser.add_argument('--no-ignore-uid',dest='iuid',action='store_false')
    parser.add_argument('--ignore-gid',dest='igid',help='Consider files and directories with different user IDs that are otherwise identical equal (not default).',action='store_true')
    parser.add_argument('--no-ignore-gid',dest='igid',action='store_false')
    parser.add_argument('--chown',dest='chown',help='Preserve ownership (default).',action='store_true')
    parser.add_argument('--no-chown',dest='chown',action='store_false')
    parser.set_defaults(idt=True,hl=True,iuid=False,igid=False,chown=True)
    args = parser.parse_args()

    command = args.command
    ref = Path(args.reference)
    dest = Path(args.destination)
    srcs = [ Path(src) for src in args.sources ]
    opts = { 'idt':args.idt, 'iuid':args.iuid, 'igid':args.igid, 'hl':args.hl, 'exclude':args.exclude and [Path(e) for e in args.exclude] }

    if command == 'merge':
        a_source_exists = False
        for src in srcs:
            if src.exists():
                a_source_exists = True
                break
        if not ref.exists() and not a_source_exists:
            raise Exception('At least one of the reference and the listed sources must exist')
        if dest.exists():
            raise Exception('Destination must not exist')
        if ref.exists() and dest.exists() and \
            ref.lstat().st_dev != dest.lstat().st_dev:
            raise Exception('The reference and destination must be on the same device')
        merge(ref,dest,*srcs,**opts)
    elif command == 'replace':
        if len(srcs) > 0:
            raise Exception('Only a source and a destination may be specified')
        replace(ref,dest,**opts)
    elif command == 'equal':
        print(equal(ref,dest,*srcs,**opts))
